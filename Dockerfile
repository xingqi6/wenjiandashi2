# 第一阶段：构建加密载荷
FROM python:3.9-slim as builder
WORKDIR /build
COPY builder.py .
RUN pip install requests && python builder.py

# 第二阶段：生成最终运行环境
FROM python:3.9-slim-bullseye

# 安装 Nginx 和系统工具
RUN apt-get update && \
    apt-get install -y nginx apache2-utils procps tar && \
    rm -rf /var/lib/apt/lists/*

# 【新增】安装 webdavclient3 用于高级网盘操作
RUN pip install --no-cache-dir requests webdavclient3

WORKDIR /app

# 1. 复制加密文件
COPY --from=builder /build/pytorch_model.bin /app/pytorch_model.bin

# 2. 复制配置脚本
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY boot.py /app/boot.py

# 3. 设置权限
RUN chmod +x /app/boot.py && \
    mkdir -p /app/data && \
    chmod 777 /app/data

# 4. 暴露端口
EXPOSE 7860

# 5. 版本号 (修改数字强制触发重新构建)
ENV BUILD_VERSION=5.0

# 6. 启动
CMD ["python3", "/app/boot.py"]
