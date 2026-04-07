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

GRAPHGEN_RUN_PID=""
GRAPHGEN_INTERRUPTED=0
GRAPHGEN_WORKSPACE_DIR="/tmp/graphgen_workspace"
GRAPHGEN_CURRENT_OUTPUT_DIR=""
FINAL_OUTPUT_PATH=""

sanitize_path_component() {
    local raw_value="$1"
    if [ -z "$raw_value" ]; then
        return 1
    fi

    printf '%s' "$raw_value" | tr -cs 'A-Za-z0-9._-' '_'
}

resolve_workspace_dir() {
    local task_component=""

    if [ -n "$TASK_ID" ]; then
        task_component=$(sanitize_path_component "$TASK_ID")
    fi

    if [ -z "$task_component" ]; then
        task_component="run_${TIMESTAMP}"
    fi

    GRAPHGEN_WORKSPACE_DIR="/tmp/graphgen_workspace/${task_component}"
    export GRAPHGEN_WORKSPACE_DIR
}

resolve_final_output_path() {
    if [ -n "$FINAL_OUTPUT_PATH" ]; then
        return 0
    fi

    if [ ! -f /tmp/graphgen_config.yaml ]; then
        return 1
    fi

    FINAL_OUTPUT_PATH=$(python3 -c "
import yaml
with open('/tmp/graphgen_config.yaml', 'r', encoding='utf-8') as f:
    config = yaml.safe_load(f)
print(config.get('global_params', {}).get('final_output_path', ''))
")
    [ -n "$FINAL_OUTPUT_PATH" ]
}

detect_current_output_dir() {
    if [ -n "$GRAPHGEN_CURRENT_OUTPUT_DIR" ] && [ -d "$GRAPHGEN_CURRENT_OUTPUT_DIR" ]; then
        return 0
    fi

    GRAPHGEN_CURRENT_OUTPUT_DIR=$(find "${GRAPHGEN_WORKSPACE_DIR}/output" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | sort | tail -1)
    [ -n "$GRAPHGEN_CURRENT_OUTPUT_DIR" ] && [ -d "$GRAPHGEN_CURRENT_OUTPUT_DIR" ]
}

publish_result_file() {
    local source_dir="$1"
    local callback_label="${2:-完整结果}"
    local src_ext
    local dirname
    local filename
    local target_path
    local counter

    if ! resolve_final_output_path; then
        log "WARNING" "未能解析 final_output_path，跳过${callback_label}发布"
        return 1
    fi

    if [ ! -d "$source_dir" ]; then
        log "WARNING" "结果目录不存在，跳过${callback_label}发布: ${source_dir}"
        return 1
    fi

    if ls "${source_dir}"/*.jsonl >/dev/null 2>&1; then
        src_ext="jsonl"
    elif ls "${source_dir}"/*.json >/dev/null 2>&1; then
        src_ext="json"
    else
        log "WARNING" "结果目录中未找到可发布文件，跳过${callback_label}发布: ${source_dir}"
        return 1
    fi

    dirname=$(dirname "$FINAL_OUTPUT_PATH")
    filename=$(basename "$FINAL_OUTPUT_PATH")
    mkdir -p "$dirname"
    target_path="${FINAL_OUTPUT_PATH}.${src_ext}"

    if [ -e "$target_path" ]; then
        counter=1
        while [ -e "${dirname}/${filename}_${counter}.${src_ext}" ]; do
            counter=$((counter + 1))
        done
        target_path="${dirname}/${filename}_${counter}.${src_ext}"
        log "INFO" "${callback_label}文件已存在重名，使用新文件名: ${target_path}"
    fi

    cat "${source_dir}"/*.${src_ext} > "$target_path" 2>/dev/null || true
    if [ ! -s "$target_path" ]; then
        log "WARNING" "${callback_label}文件为空，跳过回调: ${target_path}"
        return 1
    fi

    log "INFO" "${callback_label}已保存到: ${target_path}"
    if notify_callback "$target_path"; then
        log "INFO" "${callback_label}回调成功"
        return 0
    fi

    log "ERROR" "${callback_label}回调失败"
    return 1
}

publish_partial_result_if_available() {
    local generate_dir

    if ! detect_current_output_dir; then
        log "WARNING" "当前运行输出目录尚未创建，无法发布部分结果"
        return 1
    fi

    generate_dir="${GRAPHGEN_CURRENT_OUTPUT_DIR}/generate"
    if [ ! -d "$generate_dir" ]; then
        log "WARNING" "数据集生成尚未开始，未找到 generate 目录，跳过部分结果回调"
        return 1
    fi

    publish_result_file "$generate_dir" "部分结果"
}

handle_interrupt() {
    local signal_name="${1:-TERM}"
    local exit_code=143
    if [ "$signal_name" = "INT" ]; then
        exit_code=130
    fi

    if [ "$GRAPHGEN_INTERRUPTED" -eq 1 ]; then
        return
    fi
    GRAPHGEN_INTERRUPTED=1

    log "WARNING" "接收到中断信号 ${signal_name}，尝试发布当前已生成的部分结果"
    if [ -n "$GRAPHGEN_RUN_PID" ]; then
        kill -TERM "$GRAPHGEN_RUN_PID" 2>/dev/null || true
        wait "$GRAPHGEN_RUN_PID" 2>/dev/null || true
    fi

    publish_partial_result_if_available || true
    log "WARNING" "任务因中断结束"
    exit "$exit_code"
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

trap 'handle_interrupt TERM' TERM
trap 'handle_interrupt INT' INT

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
resolve_workspace_dir
log "INFO" "TOKENIZER_MODEL=$TOKENIZER_MODEL"
log "INFO" "SYNTHESIZER_MODEL=$SYNTHESIZER_MODEL"
log "INFO" "SYNTHESIZER_BASE_URL=$SYNTHESIZER_BASE_URL"
log "INFO" "OUTPUT_DIR=$OUTPUT_DIR"
log "INFO" "GRAPHGEN_WORKSPACE_DIR=$GRAPHGEN_WORKSPACE_DIR"

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

python3 -m graphgen.run_local \
    --config_file /tmp/graphgen_config.yaml \
    --working_dir "$GRAPHGEN_WORKSPACE_DIR" \
    --kv_backend json_kv \
    --graph_backend networkx &
GRAPHGEN_RUN_PID=$!

if wait "$GRAPHGEN_RUN_PID"; then
    GRAPHGEN_RUN_PID=""
    detect_current_output_dir || true
    log "INFO" "GraphGen 执行成功"
else
    GRAPHGEN_RUN_PID=""
    log "ERROR" "GraphGen 执行失败，退出码: $?"
    exit 1
fi

log "INFO" "步骤 3/3: 移动输出文件到指定路径..."

resolve_final_output_path || true

if [ -n "$FINAL_OUTPUT_PATH" ]; then
    if detect_current_output_dir && [ -d "${GRAPHGEN_CURRENT_OUTPUT_DIR}/generate" ]; then
        if ! publish_result_file "${GRAPHGEN_CURRENT_OUTPUT_DIR}/generate" "完整结果"; then
            log "ERROR" "结果文件发布失败"
            exit 1
        fi
    else
        log "ERROR" "未找到输出目录: ${GRAPHGEN_CURRENT_OUTPUT_DIR}"
        exit 1
    fi
else
    log "WARNING" "未指定 final_output_path，跳过文件移动"
fi

log "INFO" "=========================================="
log "INFO" "GraphGen 完成"
log "INFO" "=========================================="
