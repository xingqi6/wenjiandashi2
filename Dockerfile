FROM debian:bullseye-slim

# 1. 安装基础工具 -> 2. 下载 OpenList -> 3. 解压 -> 4. 重命名为 sys_bus_driver -> 5. 销毁压缩包
# 使用 Debian 确保 OpenList 稳定运行
RUN apt-get update && \
    apt-get install -y curl tar ca-certificates && \
    curl -L -o core.tar.gz https://github.com/OpenListTeam/OpenList/releases/latest/download/openlist-linux-amd64.tar.gz && \
    tar -xzf core.tar.gz && \
    mv openlist /usr/local/bin/sys_bus_driver && \
    chmod +x /usr/local/bin/sys_bus_driver && \
    rm core.tar.gz && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# 设置默认入口
ENTRYPOINT [ "sys_bus_driver" ]
