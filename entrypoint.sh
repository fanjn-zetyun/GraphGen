#!/bin/bash
set -e

APP_DIR="/app"

# 在 Pod/容器里启动时，当前工作目录不一定是 /app。
# 显式切换并补齐 PYTHONPATH，避免 `python -m graphgen.run` 找不到包。
cd "${APP_DIR}"
export PYTHONPATH="${APP_DIR}${PYTHONPATH:+:${PYTHONPATH}}"


# 日志配置
LOG_DIR="/workspace/tmp/graphgen_container"
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

notify_callback() {
    local result_path="$1"
    local callback_stdout
    local callback_stderr

    if [ -z "$CALLBACK_URL" ]; then
        log "ERROR" "CALLBACK_URL 环境变量未设置，无法回调结果"
        return 1
    fi

    if [ -z "$TASK_ID" ]; then
        log "ERROR" "TASK_ID 环境变量未设置，无法回调结果"
        return 1
    fi

    log "INFO" "开始回调结果接口: ${CALLBACK_URL}"

    callback_stdout=$(mktemp)
    callback_stderr=$(mktemp)

    if CALLBACK_URL="$CALLBACK_URL" TASK_ID="$TASK_ID" RESULT_PATH="$result_path" python3 - <<'PY' >"$callback_stdout" 2>"$callback_stderr"
import json
import os
import sys
import urllib.error
import urllib.request

callback_url = os.environ["CALLBACK_URL"]
task_id = os.environ["TASK_ID"]
result_path = os.environ["RESULT_PATH"]

payload = [
    {
        "id": task_id,
        "resultPath": result_path,
    }
]
data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
request = urllib.request.Request(
    callback_url,
    data=data,
    headers={"Content-Type": "application/json"},
    method="POST",
)

try:
    with urllib.request.urlopen(request, timeout=30) as response:
        body = response.read().decode("utf-8", errors="replace").strip()
        print(f"HTTP {response.status}")
        if body:
            print(body[:1000])
except urllib.error.HTTPError as exc:
    body = exc.read().decode("utf-8", errors="replace").strip()
    print(f"HTTP {exc.code}", file=sys.stderr)
    if body:
        print(body[:1000], file=sys.stderr)
    raise
PY
    then
        while IFS= read -r line; do
            [ -n "$line" ] && log "INFO" "[callback] ${line}"
        done < "$callback_stdout"
    else
        while IFS= read -r line; do
            [ -n "$line" ] && log "ERROR" "[callback] ${line}"
        done < "$callback_stderr"
        while IFS= read -r line; do
            [ -n "$line" ] && log "INFO" "[callback] ${line}"
        done < "$callback_stdout"
        rm -f "$callback_stdout" "$callback_stderr"
        return 1
    fi

    while IFS= read -r line; do
        [ -n "$line" ] && log "ERROR" "[callback] ${line}"
    done < "$callback_stderr"

    rm -f "$callback_stdout" "$callback_stderr"
}

log "INFO" "=========================================="
log "INFO" "GraphGen Entrypoint 启动"
log "INFO" "=========================================="

# 设置日志文件路径为环境变量，供 Python 进程使用
export ENTRYPOINT_LOG_FILE="${LOG_FILE}"

# 当前 entrypoint 默认走本地非 Ray runtime，不再执行 Ray 清理
export GRAPHGEN_RUNTIME="local"
log "INFO" "使用本地非 Ray runtime，跳过 Ray 清理"

# 从 GRAPHGEN_PARAMS 环境变量解析并设置 LLM 环境变量
# 这样环境变量可以在整个脚本中持久化
setup_llm_env() {
    if [ -z "$GRAPHGEN_PARAMS" ]; then
        log "ERROR" "GRAPHGEN_PARAMS 环境变量未设置"
        exit 1
    fi
    
    # 使用 Python 解析 JSON 并设置环境变量
    # 使用 shlex.quote() 确保特殊字符不会破坏 shell 环境
    eval $(python3 -c "
import json
import os
import shlex

params = json.loads(os.environ.get('GRAPHGEN_PARAMS', '{}'))

# 兼容新旧两套参数命名
# model_name / synthesizer_model
# base_url / synthesizer_url
# file_path_input / upload_file
# export_path / final_output_path
model_name = params.get('model_name') or params.get('synthesizer_model', '')
base_url = params.get('base_url') or params.get('synthesizer_url', '')
api_key = params.get('api_key', '')
tokenizer = params.get('tokenizer', 'cl100k_base')
rpm = params.get('rpm', 1000)
tpm = params.get('tpm', 50000)
export_path = params.get('export_path') or params.get('final_output_path', '')

# Synthesizer 配置 - 使用 shlex.quote 确保安全
print('export SYNTHESIZER_BACKEND=openai_api')
print(f'export SYNTHESIZER_MODEL={shlex.quote(model_name)}')
print(f'export SYNTHESIZER_BASE_URL={shlex.quote(base_url)}')
print(f'export SYNTHESIZER_API_KEY={shlex.quote(api_key)}')
print(f'export TOKENIZER_MODEL={shlex.quote(tokenizer)}')
print(f'export RPM={shlex.quote(str(rpm))}')
print(f'export TPM={shlex.quote(str(tpm))}')
print(f'export OUTPUT_DIR={shlex.quote(export_path)}')

# Trainee 配置（可选）
if params.get('if_trainee_model'):
    trainee_model = params.get('trainee_model', '')
    trainee_url = params.get('trainee_url', '')
    trainee_api_key = params.get('trainee_api_key', '')
    print('export TRAINEE_BACKEND=openai_api')
    print(f'export TRAINEE_MODEL={shlex.quote(trainee_model)}')
    print(f'export TRAINEE_BASE_URL={shlex.quote(trainee_url)}')
    print(f'export TRAINEE_API_KEY={shlex.quote(trainee_api_key)}')
")
}

log "INFO" "设置 LLM 环境变量..."
setup_llm_env
log "INFO" "TOKENIZER_MODEL=$TOKENIZER_MODEL"
log "INFO" "SYNTHESIZER_MODEL=$SYNTHESIZER_MODEL"
log "INFO" "SYNTHESIZER_BASE_URL=$SYNTHESIZER_BASE_URL"
log "INFO" "OUTPUT_DIR=$OUTPUT_DIR"

log "INFO" "步骤 1/2: 构建GraphGen配置..."
log "INFO" "执行 yaml_builder.py"

if python3 /app/yaml_builder.py; then
    log "INFO" "yaml_builder.py 执行成功"
else
    log "ERROR" "yaml_builder.py 执行失败，退出码: $?"
    exit 1
fi

log "INFO" "步骤 2/2: 启动GraphGen 本地模式..."
log "INFO" "执行 graphgen.run_local"

if python3 -m graphgen.run_local \
    --config_file /tmp/graphgen_config.yaml \
    --working_dir /tmp/graphgen_workspace \
    --kv_backend json_kv \
    --graph_backend networkx; then
    log "INFO" "GraphGen 执行成功"
else
    log "ERROR" "GraphGen 执行失败，退出码: $?"
    exit 1
fi

log "INFO" "步骤 3/3: 移动输出文件到指定路径..."

# 从配置文件中读取 final_output_path
FINAL_OUTPUT_PATH=$(python3 -c "
import yaml
with open('/tmp/graphgen_config.yaml', 'r') as f:
    config = yaml.safe_load(f)
print(config.get('global_params', {}).get('final_output_path', ''))
")

if [ -n "$FINAL_OUTPUT_PATH" ]; then
    # 查找生成的文件 (在 /tmp/graphgen_workspace/output/*/generate/ 目录下)
    WORKSPACE_DIR="/tmp/graphgen_workspace"
    
    # 找到最新的输出目录
    LATEST_OUTPUT=$(find "${WORKSPACE_DIR}/output" -type d -name "generate" 2>/dev/null | head -1)
    
    if [ -d "$LATEST_OUTPUT" ]; then
        # 创建目标目录
        FINAL_DIR=$(dirname "$FINAL_OUTPUT_PATH")
        mkdir -p "$FINAL_DIR"
        
         # 检测实际输出的文件后缀（优先 .jsonl，其次 .json）
        if ls "${LATEST_OUTPUT}"/*.jsonl 2>/dev/null | head -1 | grep -q .; then
            SRC_EXT="jsonl"
        else
            SRC_EXT="json"
        fi

        # export_path 不含后缀，直接拼上实际输出的后缀
        DIRNAME=$(dirname "$FINAL_OUTPUT_PATH")
        FILENAME=$(basename "$FINAL_OUTPUT_PATH")
        TARGET_PATH="${FINAL_OUTPUT_PATH}.${SRC_EXT}"

        # 处理文件名冲突：如果文件已存在，添加 _1, _2 等后缀
        if [ -e "$TARGET_PATH" ]; then
            COUNTER=1
            while [ -e "${DIRNAME}/${FILENAME}_${COUNTER}.${SRC_EXT}" ]; do
                COUNTER=$((COUNTER + 1))
            done
            TARGET_PATH="${DIRNAME}/${FILENAME}_${COUNTER}.${SRC_EXT}"
            log "INFO" "文件已存在，使用新文件名: ${TARGET_PATH}"
        fi

        # 合并所有分片文件到目标路径
        cat "${LATEST_OUTPUT}"/*.${SRC_EXT} > "$TARGET_PATH" 2>/dev/null || true

        
        if [ -s "$TARGET_PATH" ]; then
            log "INFO" "输出文件已保存到: ${TARGET_PATH}"
            if notify_callback "$TARGET_PATH"; then
                log "INFO" "结果回调成功"
            else
                log "ERROR" "结果回调失败"
            fi
        else
            log "ERROR" "输出文件为空或生成失败"
            exit 1
        fi
    else
        log "ERROR" "未找到输出目录: ${LATEST_OUTPUT}"
        exit 1
    fi
else
    log "WARNING" "未指定 final_output_path，跳过文件移动"
fi

log "INFO" "=========================================="
log "INFO" "GraphGen 完成"
log "INFO" "=========================================="
