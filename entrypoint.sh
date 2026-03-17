#!/bin/bash
set -e

# 日志配置
LOG_DIR="/app/container_logs"
TIMESTAMP=$(date '+%Y-%m-%d_%H-%M-%S')
LOG_FILE="${LOG_DIR}/entrypoint_${TIMESTAMP}.log"

# 创建日志目录
mkdir -p "${LOG_DIR}"

# 日志函数
log() {
    local level=$1
    shift
    local message="$@"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[${timestamp}] [${level}] ${message}" | tee -a "${LOG_FILE}"
}

log "INFO" "=========================================="
log "INFO" "GraphGen Entrypoint 启动"
log "INFO" "=========================================="

log "INFO" "步骤 1/2: 构建GraphGen配置..."
log "INFO" "执行 yaml_builder.py"

if python3 /app/yaml_builder.py; then
    log "INFO" "yaml_builder.py 执行成功"
else
    log "ERROR" "yaml_builder.py 执行失败，退出码: $?"
    exit 1
fi

log "INFO" "步骤 2/2: 启动GraphGen..."
log "INFO" "执行 graphgen.run"

if python3 -m graphgen.run --config_file /tmp/graphgen_config.yaml; then
    log "INFO" "GraphGen 执行成功"
else
    log "ERROR" "GraphGen 执行失败，退出码: $?"
    exit 1
fi

log "INFO" "=========================================="
log "INFO" "GraphGen 完成"
log "INFO" "=========================================="
