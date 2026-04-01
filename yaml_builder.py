#!/usr/bin/env python3
"""
从标准输入或文件读取JSON参数，构建GraphGen YAML配置文件
复用webui/app.py中的配置构建逻辑
"""
import json
import yaml
import os
import sys
import logging
from datetime import datetime

# 固定的输出目录
# OUTPUT_DIR = "/workspace/user-data/datasets"
LOG_DIR = "/app/container_logs"

# 配置日志
def setup_logging():
    """配置日志记录器，使用 entrypoint.sh 设置的日志文件"""
    os.makedirs(LOG_DIR, exist_ok=True)

    # 优先使用 entrypoint.sh 设置的日志文件路径
    log_file = os.environ.get("ENTRYPOINT_LOG_FILE")
    if not log_file:
        # 如果没有设置，则创建独立的日志文件（兼容独立运行场景）
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        log_file = os.path.join(LOG_DIR, f"yaml_builder_{timestamp}.log")

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    return logging.getLogger(__name__)

logger = setup_logging()

def load_params():
    """
    从多种来源读取参数：
    1. 环境变量 GRAPHGEN_PARAMS（JSON字符串）
    2. 文件 /config/params.json
    3. 标准输入
    """
    logger.info("开始加载参数...")

    # 方式1：环境变量
    if "GRAPHGEN_PARAMS" in os.environ:
        logger.info("从环境变量 GRAPHGEN_PARAMS 读取参数")
        params = json.loads(os.environ["GRAPHGEN_PARAMS"])
        logger.info("成功从环境变量加载参数")
        return params

    # 方式2：配置文件
    if os.path.exists("/config/params.json"):
        logger.info("从配置文件 /config/params.json 读取参数")
        with open("/config/params.json", "r") as f:
            params = json.load(f)
        logger.info("成功从配置文件加载参数")
        return params

    # 方式3：标准输入
    if not sys.stdin.isatty():
        logger.info("从标准输入读取参数")
        params = json.load(sys.stdin)
        logger.info("成功从标准输入加载参数")
        return params

    error_msg = "No parameters provided. Set GRAPHGEN_PARAMS env var, mount /config/params.json, or pipe JSON to stdin."
    logger.error(error_msg)
    raise Exception(error_msg)

def get_partition_params(params):
    """根据分区方法提取对应参数（复用webui/app.py逻辑）"""
    method = params.get("partition_method", "ece")
    logger.info(f"使用分区方法: {method}")

    if method == "dfs":
        partition_params = {"max_units_per_community": params.get("dfs_max_units", 5)}
    elif method == "bfs":
        partition_params = {"max_units_per_community": params.get("bfs_max_units", 5)}
    elif method == "leiden":
        partition_params = {
            "max_size": params.get("leiden_max_size", 20),
            "use_lcc": params.get("leiden_use_lcc", False),
            "random_seed": params.get("leiden_random_seed", 42),
        }
    else:  # ece
        partition_params = {
            "max_units_per_community": params.get("ece_max_units", 20),
            "min_units_per_community": params.get("ece_min_units", 3),
            "max_tokens_per_community": params.get("ece_max_tokens", 10240),
            "unit_sampling": params.get("ece_unit_sampling", "random"),
        }

    logger.debug(f"分区参数: {partition_params}")
    return partition_params

def build_config(params):
    """构建GraphGen YAML配置（复用webui/app.py逻辑）"""
    logger.info("开始构建GraphGen配置...")

    # 兼容新旧两套参数命名
    # model_name / synthesizer_model
    # base_url / synthesizer_url
    # file_path_input / upload_file
    # export_path / final_output_path
    model_name = params.get('model_name') or params.get('synthesizer_model', '')
    base_url = params.get('base_url') or params.get('synthesizer_url', '')
    api_key = params.get('api_key', '')
    file_path_input = params.get('file_path_input') or params.get('upload_file', '')
    export_path = params.get('export_path') or params.get('final_output_path', '')

    # 设置环境变量（LLM配置）
    logger.info("设置LLM环境变量...")
    os.environ["SYNTHESIZER_BACKEND"] = "openai_api"
    os.environ["SYNTHESIZER_MODEL"] = model_name
    os.environ["SYNTHESIZER_BASE_URL"] = base_url
    os.environ["SYNTHESIZER_API_KEY"] = api_key
    os.environ["TOKENIZER_MODEL"] = params.get("tokenizer", "cl100k_base")
    os.environ["RPM"] = str(params.get("rpm", 1000))
    os.environ["TPM"] = str(params.get("tpm", 50000))

    logger.info(f"Synthesizer模型: {model_name}")
    logger.info(f"Synthesizer URL: {base_url}")

    if params.get("if_trainee_model"):
        logger.info("配置Trainee模型...")
        os.environ["TRAINEE_BACKEND"] = "openai_api"
        os.environ["TRAINEE_MODEL"] = params["trainee_model"]
        os.environ["TRAINEE_BASE_URL"] = params["trainee_url"]
        os.environ["TRAINEE_API_KEY"] = params["trainee_api_key"]
        logger.info(f"Trainee模型: {params['trainee_model']}")

    # 构建节点列表（复用webui/app.py的DAG构建逻辑）
    logger.info("构建DAG节点...")
    nodes = [
        {
            "id": "read",
            "op_name": "read",
            "type": "source",
            "dependencies": [],
            "params": {"input_path": [file_path_input]},
        },
        {
            "id": "chunk",
            "op_name": "chunk",
            "type": "map_batch",
            "dependencies": ["read"],
            "execution_params": {"replicas": 1},
            "params": {
                "chunk_size": params.get("chunk_size", 1024),
                "chunk_overlap": params.get("chunk_overlap", 100),
            },
        },
        {
            "id": "build_kg",
            "op_name": "build_kg",
            "type": "map_batch",
            "dependencies": ["chunk"],
            "execution_params": {"replicas": 1, "batch_size": 128},
        },
    ]

    last_node_id = "build_kg"
    logger.info(f"基础节点构建完成: read -> chunk -> build_kg")

    # 可选：quiz和judge节点
    if params.get("if_trainee_model"):
        logger.info("添加quiz和judge节点...")
        nodes.extend([
            {
                "id": "quiz",
                "op_name": "quiz",
                "type": "aggregate",
                "dependencies": ["build_kg"],
                "execution_params": {"replicas": 1, "batch_size": 128},
                "params": {"quiz_samples": params.get("quiz_samples", 2)},
            },
            {
                "id": "judge",
                "op_name": "judge",
                "type": "map_batch",
                "dependencies": ["quiz"],
                "execution_params": {"replicas": 1, "batch_size": 128},
            }
        ])
        last_node_id = "judge"
        logger.info("quiz和judge节点添加完成")

    # Partition节点
    logger.info("添加partition节点...")
    partition_params = get_partition_params(params)
    nodes.append({
        "id": "partition",
        "op_name": "partition",
        "type": "aggregate",
        "dependencies": [last_node_id],
        "params": {
            "method": params.get("partition_method", "ece"),
            "method_params": partition_params,
        },
    })

    # Generate节点
    logger.info("添加generate节点...")
    nodes.append({
        "id": "generate",
        "op_name": "generate",
        "type": "map_batch",
        "dependencies": ["partition"],
        "save_output": True,
        "execution_params": {"replicas": 1, "batch_size": 128},
        "params": {
            "method": params.get("mode", "aggregated"),
            "data_format": params.get("data_format", "Alpaca"),
        },
    })

    # 完整配置
    logger.info("组装完整配置...")
    # 使用固定的临时工作目录，最终输出路径由 final_output_path 指定
    working_dir = "/tmp/graphgen_workspace"
    config = {
        "global_params": {
            "working_dir": working_dir,
            "graph_backend": "kuzu",
            "kv_backend": params.get("kv_backend", "json_kv"),  # 默认使用 json_kv 避免 rocksdb 崩溃
            "final_output_path": export_path,  # 用户指定的最终输出路径
        },
        "nodes": nodes,
    }

    logger.info(f"配置构建完成，共 {len(nodes)} 个节点")
    return config

def main():
    logger.info("=" * 60)
    logger.info("YAML Builder 启动")
    logger.info("=" * 60)

    try:
        # 1. 读取参数
        params = load_params()
        logger.info("参数加载成功")
        print("Loaded parameters:")
        print(json.dumps(params, indent=2, ensure_ascii=False))

        # 2. 构建配置
        config = build_config(params)
        logger.info("配置构建成功")

        # 3. 写入YAML文件
        output_file = "/tmp/graphgen_config.yaml"
        logger.info(f"写入配置文件: {output_file}")
        with open(output_file, "w") as f:
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True)

        logger.info(f"配置文件生成成功: {output_file}")
        print(f"\nGenerated config file: {output_file}")
        print("Config content:")
        with open(output_file, "r") as f:
            print(f.read())

        logger.info("=" * 60)
        logger.info("YAML Builder 完成")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"YAML Builder 执行失败: {str(e)}", exc_info=True)
        raise

if __name__ == "__main__":
    main()
