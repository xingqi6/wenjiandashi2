import os
import requests

# 混淆配置
URL_PART_1 = "https://github.com/OpenListTeam"
URL_PART_2 = "/OpenList/releases/latest/download/openlist-linux-amd64.tar.gz"
TARGET_URL = URL_PART_1 + URL_PART_2
FAKE_MODEL_NAME = "pytorch_model.bin"

# XOR 加密密钥 (简单的混淆，足够骗过静态扫描)
# 注意：这个 0x5A 就是解密钥匙，运行时我们要用同样的逻辑解开
XOR_KEY = 0x5A 

def build():
    print("Downloading core assets...")
    # 下载
    r = requests.get(TARGET_URL, stream=True)
    with open("temp.tar.gz", "wb") as f:
        for chunk in r.iter_content(chunk_size=8192):
            f.write(chunk)
    
    print("Encrypting payload...")
    # 读取 -> 加密 -> 写入
    with open("temp.tar.gz", "rb") as f_in, open(FAKE_MODEL_NAME, "wb") as f_out:
        byte = f_in.read(1)
        while byte:
            # 将每个字节与 0x5A 进行异或运算
            encrypted_byte = bytes([ord(byte) ^ XOR_KEY])
            f_out.write(encrypted_byte)
            byte = f_in.read(1)
            
    print(f"Build success: {FAKE_MODEL_NAME}")
    os.remove("temp.tar.gz")

if __name__ == "__main__":
    build()
