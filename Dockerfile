FROM registry.hd-02.alayanew.com:8443/alayanew-4fd285c4-c4f3-4e92-80ee-26169717cba8/graphgen:1.7



# 复制 GraphGen 源码
COPY . .

RUN chmod +x /app/entrypoint.sh