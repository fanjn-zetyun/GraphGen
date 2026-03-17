#!/bin/bash

# ==================== 基础配置 ====================
IMAGE_NAME="graphgen-worker:latest"
CONTAINER_NAME="graphgen-test"

# ==================== 测试参数 ====================
# 输入文件目录（宿主机路径）
INPUT_DIR="./examples/data"
INPUT_FILE="test.jsonl"

# LLM配置
SYNTHESIZER_MODEL="gpt-4o-mini"
SYNTHESIZER_URL="https://api.openai.com/v1"
API_KEY="your-api-key-here"

# 分区配置
PARTITION_METHOD="ece"
CHUNK_SIZE=1024
CHUNK_OVERLAP=100

# 生成配置
MODE="aggregated"
DATA_FORMAT="Alpaca"

# 可选：Trainee模型配置（不使用则留空）
IF_TRAINEE_MODEL=false
TRAINEE_MODEL=""
TRAINEE_URL=""
TRAINEE_API_KEY=""

# ==================== 构建JSON参数 ====================
GRAPHGEN_PARAMS=$(cat <<EOF
{
  "synthesizer_model": "${SYNTHESIZER_MODEL}",
  "synthesizer_url": "${SYNTHESIZER_URL}",
  "api_key": "${API_KEY}",
  "upload_file": "/workspace/input/${INPUT_FILE}",
  "partition_method": "${PARTITION_METHOD}",
  "chunk_size": ${CHUNK_SIZE},
  "chunk_overlap": ${CHUNK_OVERLAP},
  "mode": "${MODE}",
  "data_format": "${DATA_FORMAT}",
  "ece_max_units": 20,
  "ece_min_units": 3,
  "ece_max_tokens": 10240,
  "if_trainee_model": ${IF_TRAINEE_MODEL}
}
EOF
)

# ==================== Docker运行命令 ====================
docker run --rm \
  --name ${CONTAINER_NAME} \
  -e GRAPHGEN_PARAMS="${GRAPHGEN_PARAMS}" \
  -v "${INPUT_DIR}:/workspace/input:ro" \
  -v "./output:/workspace/user-data/dataset" \
  -v "./logs:/app/container_logs" \
  ${IMAGE_NAME}
