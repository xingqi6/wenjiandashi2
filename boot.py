import os
import subprocess
import time
import sys

# ==========================================
# 1. 配置区域
# ==========================================
XOR_KEY = 0x5A 
ENCRYPTED_FILE = "pytorch_model.bin"
DECRYPTED_TAR = "release.tar.gz"
BINARY_NAME = "inference_engine" 

def log(msg):
    print(f"[System] {msg}", flush=True)

# ==========================================
# 2. 动态生成无弹窗 Nginx 配置
# ==========================================
def write_nginx_config():
    # 获取密码
    password = os.environ.get("AUTH_PASS", "password").strip()
    log("Overwriting Nginx config with Stealth-Mode...")

    # 这是一个完全没有 auth_basic (弹窗) 的配置
    # 采用了 Cookie 隐形门策略
    config_content = f"""
error_log /dev/stderr warn;

server {{
    listen 7860;
    server_name localhost;

    # A. 隐形门入口: /auth?key=密码
    location = /auth {{
        if ($arg_key != "{password}") {{
            add_header Content-Type text/plain;
            return 401 "Access Denied";
        }}
        # 种下 Cookie
        add_header Set-Cookie "access_token=granted; Path=/; Max-Age=2592000; HttpOnly";
        # 跳转首页
        return 302 /;
    }}

    # B. 主页入口
    location / {{
        # 没有 Cookie 就显示伪装页
        if ($cookie_access_token != "granted") {{
            add_header Content-Type text/plain;
            return 200 "System Maintenance. Service Offline.";
        }}

        # 有 Cookie，转发给 OpenList
        proxy_pass http://127.0.0.1:5244;

        # 【核心】：强制屏蔽 OpenList 的 401 弹窗信号
        proxy_hide_header WWW-Authenticate;
        proxy_set_header Authorization "";

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        proxy_buffering off;
        client_max_body_size 0;
    }}
}}
"""
    # 直接写入系统路径，覆盖掉任何旧文件
    with open("/etc/nginx/conf.d/default.conf", "w") as f:
        f.write(config_content)
    log("Nginx config updated successfully.")

# ==========================================
# 3. 解密与启动逻辑
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
    
    # 写入最新的 Nginx 配置
    write_nginx_config()

    # 初始化 OpenList
    if not os.path.exists("data/config.json"):
        try:
            subprocess.run([f"./{BINARY_NAME}", "server"], timeout=3, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except: pass
            
    if os.path.exists("data/config.json"):
        subprocess.run("sed -i 's/\"http_port\": [0-9]*/\"http_port\": 5244/' data/config.json", shell=True)
        subprocess.run("sed -i 's/\"address\": \".*\"/\"address\": \"0.0.0.0\"/' data/config.json", shell=True)

    password = os.environ.get("AUTH_PASS", "password").strip()
    subprocess.run([f"./{BINARY_NAME}", "admin", "set", password], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    # 启动 OpenList
    with open("engine.log", "w") as logfile:
        subprocess.Popen([f"./{BINARY_NAME}", "server"], stdout=logfile, stderr=logfile)
    
    time.sleep(3)
    
    # 启动 Nginx
    log("Starting Gateway...")
    subprocess.run(["nginx", "-g", "daemon off;"])

# 👇👇👇 你的代码里肯定缺了下面这两行 👇👇👇
if __name__ == "__main__":
    start_services()
