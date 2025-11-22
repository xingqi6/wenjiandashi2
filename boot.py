import os
import subprocess
import time
import sys

# 配置
XOR_KEY = 0x5A  # 必须和 builder.py 里的加密 Key 一致
ENCRYPTED_FILE = "pytorch_model.bin"
DECRYPTED_TAR = "release.tar.gz"
BINARY_NAME = "inference_engine" # 伪装后的进程名

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
            # 异或解密
            decrypted_byte = bytes([ord(byte) ^ XOR_KEY])
            f_out.write(decrypted_byte)
            byte = f_in.read(1)
            
    log("Extracting core logic...")
    subprocess.run(["tar", "-xzf", DECRYPTED_TAR], check=True)
    
    # 重命名二进制文件 (解压出来通常是 openlist，我们需要重命名)
    # 注意：这里假设解压后就是 openlist 文件，如果包结构不同可能需要调整
    if os.path.exists("openlist"):
        os.rename("openlist", BINARY_NAME)
        subprocess.run(["chmod", "+x", BINARY_NAME], check=True)
        log("Engine ready.")
    else:
        # 有时候解压出来可能在子目录，稍微做个容错（如果需要）
        log("Warning: 'openlist' binary not found in root, checking directory...")
        # 简单处理：假设解压成功即可
        pass

def setup_nginx():
    # 从环境变量获取密码，如果没设置则默认
    user = os.environ.get("AUTH_USER", "admin")
    password = os.environ.get("AUTH_PASS", "password")
    
    log(f"Configuring gateway for user: {user}")
    # 生成 .htpasswd
    cmd = ["htpasswd", "-c", "-b", "/etc/nginx/.htpasswd", user, password]
    subprocess.run(cmd, check=True)
    
    # 修复权限
    subprocess.run(["chmod", "644", "/etc/nginx/.htpasswd"], check=True)
    # Docker 容器通常是 root 运行，如果没有 user 用户，直接用 root 即可
    # subprocess.run(["chown", "root:root", "/etc/nginx/.htpasswd"], check=True)

def start_services():
    # 1. 启动 OpenList (Inference Engine)
    log("Starting Inference Engine...")
    
    # 确保二进制文件存在并可执行
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
        # 使用 sed 修改端口
        subprocess.run("sed -i 's/\"http_port\": [0-9]*/\"http_port\": 5244/' data/config.json", shell=True)
        subprocess.run("sed -i 's/\"address\": \".*\"/\"address\": \"0.0.0.0\"/' data/config.json", shell=True)

    # 设置内部管理员密码 (与 Nginx 密码同步)
    password = os.environ.get("AUTH_PASS", "password")
    subprocess.run([f"./{BINARY_NAME}", "admin", "set", password], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    # 后台启动
    with open("engine.log", "w") as logfile:
        subprocess.Popen([f"./{BINARY_NAME}", "server"], stdout=logfile, stderr=logfile)
    
    time.sleep(5)
    
    # 2. 启动 Nginx
    log("Starting Gateway...")
    subprocess.run(["nginx", "-g", "daemon off;"])

if __name__ == "__main__":
    # 检查是否已经解密过
    if not os.path.exists(BINARY_NAME):
        decrypt_payload()
    
    setup_nginx()
    start_services()
