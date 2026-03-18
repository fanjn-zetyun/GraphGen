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

# 设置日志文件路径为环境变量，供 Python 进程使用
export ENTRYPOINT_LOG_FILE="${LOG_FILE}"

# 从 GRAPHGEN_PARAMS 环境变量解析并设置 LLM 环境变量
# 这样环境变量可以在整个脚本中持久化
setup_llm_env() {
    if [ -z "$GRAPHGEN_PARAMS" ]; then
        log "ERROR" "GRAPHGEN_PARAMS 环境变量未设置"
        exit 1
    fi
    
    # 使用 Python 解析 JSON 并设置环境变量
    eval $(python3 -c "
import json
import os

params = json.loads(os.environ.get('GRAPHGEN_PARAMS', '{}'))

# Synthesizer 配置
print('export SYNTHESIZER_BACKEND=openai_api')
print(f\"export SYNTHESIZER_MODEL={params.get('synthesizer_model', '')}\")
print(f\"export SYNTHESIZER_BASE_URL={params.get('synthesizer_url', '')}\")
print(f\"export SYNTHESIZER_API_KEY={params.get('api_key', '')}\")
print(f\"export TOKENIZER_MODEL={params.get('tokenizer', 'cl100k_base')}\")
print(f\"export RPM={params.get('rpm', 1000)}\")
print(f\"export TPM={params.get('tpm', 50000)}\")

# Trainee 配置（可选）
if params.get('if_trainee_model'):
    print(f\"export TRAINEE_BACKEND=openai_api\")
    print(f\"export TRAINEE_MODEL={params.get('trainee_model', '')}\")
    print(f\"export TRAINEE_BASE_URL={params.get('trainee_url', '')}\")
    print(f\"export TRAINEE_API_KEY={params.get('trainee_api_key', '')}\")
")
}

log "INFO" "设置 LLM 环境变量..."
setup_llm_env
log "INFO" "SYNTHESIZER_MODEL=$SYNTHESIZER_MODEL"
log "INFO" "SYNTHESIZER_BASE_URL=$SYNTHESIZER_BASE_URL"

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
