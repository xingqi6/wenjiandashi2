import os
import subprocess
import time
import sys
import threading
import tarfile
import shutil
from datetime import datetime
from webdav3.client import Client

# ==========================================
# 1. 配置区域
# ==========================================
XOR_KEY = 0x5A 
ENCRYPTED_FILE = "pytorch_model.bin"
DECRYPTED_TAR = "release.tar.gz"
BINARY_NAME = "inference_engine" 
BACKUP_PREFIX = "sys_snapshot_" 

def log(msg):
    print(f"[System] {msg}", flush=True)

# ==========================================
# 2. 智能 WebDAV 客户端 (支持轮转 + 自定义时间)
# ==========================================
def get_webdav_client():
    url = os.environ.get("WEBDAV_URL", "").strip()
    user = os.environ.get("WEBDAV_USER", "").strip()
    pwd = os.environ.get("WEBDAV_PASS", "").strip()
    path = os.environ.get("WEBDAV_PATH", "sys_backup").strip("/")
    
    if not url: return None, None
    
    options = {
        'webdav_hostname': url,
        'webdav_login': user,
        'webdav_password': pwd,
        'disable_check': True
    }
    return Client(options), path

def restore_data():
    client, remote_dir = get_webdav_client()
    if not client:
        log("WebDAV not configured. Skipping restore.")
        return

    try:
        log(f"Checking remote storage: /{remote_dir} ...")
        if not client.check(remote_dir):
            log("Remote directory not found. New deployment.")
            return

        files = client.list(remote_dir)
        backups = [f for f in files if f.startswith(BACKUP_PREFIX) and f.endswith(".bin")]
        
        if not backups:
            log("No backup files found.")
            return

        latest_backup = sorted(backups)[-1]
        remote_path = f"{remote_dir}/{latest_backup}"
        
        log(f"Restoring from: {latest_backup}")
        client.download_sync(remote_path=remote_path, local_path="temp_restore.tar.gz")
        
        if os.path.exists("data"): shutil.rmtree("data")
        os.makedirs("data", exist_ok=True)
        
        with tarfile.open("temp_restore.tar.gz", "r:gz") as tar:
            tar.extractall("data")
            
        os.remove("temp_restore.tar.gz")
        log("System state restored successfully.")

    except Exception as e:
        log(f"Restore Error: {str(e)}")

def backup_worker():
    # 获取自定义备份间隔 (默认 3600 秒)
    try:
        interval = int(os.environ.get("SYNC_INTERVAL", "3600"))
    except:
        interval = 3600
    
    # 安全限制：最小 60 秒
    if interval < 60: 
        interval = 60
        log("Warning: SYNC_INTERVAL too low, reset to 60s.")
    
    log(f"Backup scheduler started. Interval: {interval} seconds.")

    # 启动后延迟 2 分钟进行第一次尝试，避免抢占启动资源
    time.sleep(120)
    
    while True:
        try:
            client, remote_dir = get_webdav_client()
            if client and os.path.exists("data"):
                # 1. 检查目录
                if not client.check(remote_dir):
                    client.mkdir(remote_dir)
                
                # 2. 打包
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"{BACKUP_PREFIX}{timestamp}.bin"
                
                with tarfile.open("temp_backup.tar.gz", "w:gz") as tar:
                    tar.add("data", arcname=".")
                
                # 3. 上传
                log(f"Uploading backup: {filename}")
                client.upload_sync(remote_path=f"{remote_dir}/{filename}", local_path="temp_backup.tar.gz")
                os.remove("temp_backup.tar.gz")
                
                # 4. 轮转 (保留最新的 5 个)
                files = client.list(remote_dir)
                backups = sorted([f for f in files if f.startswith(BACKUP_PREFIX) and f.endswith(".bin")])
                
                if len(backups) > 5:
                    to_delete = backups[:-5]
                    for f in to_delete:
                        log(f"Rotating old backup: {f}")
                        client.clean(f"{remote_dir}/{f}")
                
                log("Backup cycle complete.")
            
        except Exception as e:
            log(f"Backup failed: {str(e)}")
        
        # 等待自定义的时间
        time.sleep(interval)

# ==========================================
# 3. Nginx 配置逻辑
# ==========================================
def write_nginx_config():
    password = os.environ.get("AUTH_PASS", "password").strip()
    log("Configuring Stealth Gateway...")

    config_content = f"""
error_log /dev/stderr warn;
server {{
    listen 7860;
    server_name localhost;
    location = /auth {{
        if ($arg_key != "{password}") {{
            add_header Content-Type text/plain;
            return 401 "Access Denied";
        }}
        add_header Set-Cookie "access_token=granted; Path=/; Max-Age=2592000; HttpOnly";
        return 302 /;
    }}
    location / {{
        if ($cookie_access_token != "granted") {{
            add_header Content-Type text/plain;
            return 200 "System Maintenance. Service Offline.";
        }}
        proxy_pass http://127.0.0.1:5244;
        # 允许 OpenList 接收 Token
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_buffering off;
        client_max_body_size 0;
    }}
}}
"""
    with open("/etc/nginx/conf.d/default.conf", "w") as f:
        f.write(config_content)

# ==========================================
# 4. 主启动流程
# ==========================================
def decrypt_payload():
    if not os.path.exists(ENCRYPTED_FILE):
        if os.path.exists(BINARY_NAME): return
        log("Error: Model file missing.")
        sys.exit(1)
    
    log("Decrypting payload...")
    with open(ENCRYPTED_FILE, "rb") as f_in, open(DECRYPTED_TAR, "wb") as f_out:
        byte = f_in.read(1)
        while byte:
            f_out.write(bytes([ord(byte) ^ XOR_KEY]))
            byte = f_in.read(1)
            
    subprocess.run(["tar", "-xzf", DECRYPTED_TAR], check=True)
    
    if os.path.exists("openlist"):
        os.rename("openlist", BINARY_NAME)
    elif os.path.exists("alist"):
        os.rename("alist", BINARY_NAME)
        
    subprocess.run(["chmod", "+x", BINARY_NAME], check=True)

def start_services():
    if not os.path.exists(BINARY_NAME):
        decrypt_payload()
    
    # 1. 恢复数据
    restore_data()
    
    # 2. 写 Nginx
    write_nginx_config()

    # 3. 初始化 OpenList
    if not os.path.exists("data/config.json"):
        try:
            subprocess.run([f"./{BINARY_NAME}", "server"], timeout=3, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except: pass
            
    if os.path.exists("data/config.json"):
        subprocess.run("sed -i 's/\"http_port\": [0-9]*/\"http_port\": 5244/' data/config.json", shell=True)
        subprocess.run("sed -i 's/\"address\": \".*\"/\"address\": \"0.0.0.0\"/' data/config.json", shell=True)

    password = os.environ.get("AUTH_PASS", "password").strip()
    subprocess.run([f"./{BINARY_NAME}", "admin", "set", password], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    # 4. 后台启动 OpenList
    with open("engine.log", "w") as logfile:
        subprocess.Popen([f"./{BINARY_NAME}", "server"], stdout=logfile, stderr=logfile)
    
    # 5. 启动备份线程
    t = threading.Thread(target=backup_worker, daemon=True)
    t.start()

    time.sleep(3)
    
    # 6. 启动 Nginx
    log("Starting Gateway...")
    subprocess.run(["nginx", "-g", "daemon off;"])

if __name__ == "__main__":
    start_services()
