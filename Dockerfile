FROM swr.cn-north-4.myhuaweicloud.com/ddn-k8s/docker.io/python:3.12-slim

WORKDIR /app

# 设置环境变量
ARG DEBIAN_FRONTEND=noninteractive
ENV TZ=Asia/Shanghai \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# 配置镜像源、时区并安装依赖（合并为单层以减少镜像大小）
RUN sed -i 's|http://deb.debian.org|https://mirrors.aliyun.com|g; s|http://security.debian.org|https://mirrors.aliyun.com|g' /etc/apt/sources.list.d/debian.sources 2>/dev/null || \
    sed -i 's|http://.*.debian.org|https://mirrors.aliyun.com|g' /etc/apt/sources.list.d/debian.sources 2>/dev/null || true && \
    ln -sf /usr/share/zoneinfo/Asia/Shanghai /etc/localtime && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
    curl wget net-tools git cmake \
    poppler-utils tesseract-ocr tesseract-ocr-chi-sim \
    libopenblas-dev ninja-build build-essential \
    pkg-config rclone tmux moreutils file \
    openssh-server vim telnet iputils-ping unzip bzip2 \
    librdmacm1 libibverbs1 ibverbs-providers libgl1 && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# 复制依赖文件并安装（利用 Docker 缓存）
# COPY requirements.txt .


# 复制 GraphGen 源码
COPY . .

RUN pip install --no-cache-dir -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/ && \
    rm -rf /root/.cache/pip
# 复制构建脚本和入口点
# COPY yaml_builder.py /app/yaml_builder.py
# COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# 入口点
ENTRYPOINT ["/app/entrypoint.sh"]
