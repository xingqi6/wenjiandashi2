# 第一阶段：构建加密载荷 (必须保留！)
FROM python:3.9-slim as builder
WORKDIR /build
COPY builder.py .
RUN pip install requests && python builder.py

# 第二阶段：生成最终运行环境
FROM python:3.9-slim-bullseye

# 安装 Nginx 和必要工具
RUN apt-get update && \
    apt-get install -y nginx apache2-utils procps && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 1. 从第一阶段复制加密后的伪装模型文件
COPY --from=builder /build/pytorch_model.bin /app/pytorch_model.bin

# 2. 复制配置文件
# (boot.py 会在运行时动态重写 nginx 配置，但为了构建不报错，这里必须 COPY)
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY boot.py /app/boot.py

# 3. 设置权限
RUN chmod +x /app/boot.py && \
    mkdir -p /app/data && \
    chmod 777 /app/data

# 4. 暴露端口
EXPOSE 7860

# 5. 强制刷新缓存标记 (每次修改这个版本号，HF 就会重新部署)
ENV BUILD_VERSION=3.0

# 6. 启动命令
CMD ["python3", "/app/boot.py"]
