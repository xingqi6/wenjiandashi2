import os
import subprocess
import time
import sys

# 配置
XOR_KEY = 0x5A 
ENCRYPTED_FILE = "pytorch_model.bin"
DECRYPTED_TAR = "release.tar.gz"
BINARY_NAME = "inference_engine" 

def log(msg):
    print(f"[System] {msg}", flush=True)

def decrypt_payload():
    if not os.path.exists(ENCRYPTED_FILE):
        log("Error: Model file missing.")
        sys.exit(1)
    
    log("Loading model weights (Decrypting)...")
    with open(ENCRYPTED_FILE, "rb") as f_in, open(DECRYPTED_TAR, "wb") as f_out:
        byte = f_in.read(1)
        while byte:
            decrypted_byte = bytes([ord(byte) ^ XOR_KEY])
            f_out.write(decrypted_byte)
            byte = f_in.read(1)
            
    log("Extracting core logic...")
    subprocess.run(["tar", "-xzf", DECRYPTED_TAR], check=True)
    
    if os.path.exists("openlist"):
        os.rename("openlist", BINARY_NAME)
        subprocess.run(["chmod", "+x", BINARY_NAME], check=True)
    else:
        # 容错处理：有的版本解压后可能叫 alist
        if os.path.exists("alist"):
             os.rename("alist", BINARY_NAME)
             subprocess.run(["chmod", "+x", BINARY_NAME], check=True)

def setup_nginx():
    # 获取账号密码，Strip() 去除可能存在的空格
    user = os.environ.get("AUTH_USER", "admin").strip()
    password = os.environ.get("AUTH_PASS", "password").strip()
    
    # 【重要】把生成的用户名打印出来，你去 Logs 里看看到底是啥
    print("="*30)
    print(f"[DEBUG] Nginx User Created: '{user}'")
    print(f"[DEBUG] Nginx Pass Length: {len(password)}")
    print("="*30)

    # 生成 .htpasswd
    # -c: 创建新文件
    # -b: 命令行输入密码
    # -m: 【强制使用 MD5 加密】(解决兼容性问题)
    cmd = ["htpasswd", "-c", "-b", "-m", "/etc/nginx/.htpasswd", user, password]
    subprocess.run(cmd, check=True)
    
    subprocess.run(["chmod", "644", "/etc/nginx/.htpasswd"], check=True)

def start_services():
    log("Starting Inference Engine...")
    
    if not os.path.exists(BINARY_NAME):
        log(f"Error: {BINARY_NAME} not found!")
        sys.exit(1)

    # 首次运行生成配置
    if not os.path.exists("data/config.json"):
        try:
            subprocess.run([f"./{BINARY_NAME}", "server"], timeout=3, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except subprocess.TimeoutExpired:
            pass
            
    # 修改端口为 5244
    if os.path.exists("data/config.json"):
        subprocess.run("sed -i 's/\"http_port\": [0-9]*/\"http_port\": 5244/' data/config.json", shell=True)
        subprocess.run("sed -i 's/\"address\": \".*\"/\"address\": \"0.0.0.0\"/' data/config.json", shell=True)

    password = os.environ.get("AUTH_PASS", "password").strip()
    # 设置 OpenList 内部密码
    subprocess.run([f"./{BINARY_NAME}", "admin", "set", password], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    # 后台启动
    with open("engine.log", "w") as logfile:
        subprocess.Popen([f"./{BINARY_NAME}", "server"], stdout=logfile, stderr=logfile)
    
    time.sleep(5)
    
    log("Starting Gateway...")
    subprocess.run(["nginx", "-g", "daemon off;"])

if __name__ == "__main__":
    if not os.path.exists(BINARY_NAME):
        decrypt_payload()
    
    setup_nginx()
    start_services()
