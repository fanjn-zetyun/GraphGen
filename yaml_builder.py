#!/usr/bin/env python3
"""
从标准输入或文件读取JSON参数，构建GraphGen YAML配置文件
复用webui/app.py中的配置构建逻辑
"""
import json
import yaml
import os
import sys

# 固定的输出目录
OUTPUT_DIR = "/workspace/user-data/dataset"

def load_params():
    """
    从多种来源读取参数：
    1. 环境变量 GRAPHGEN_PARAMS（JSON字符串）
    2. 文件 /config/params.json
    3. 标准输入
    """
    # 方式1：环境变量
    if "GRAPHGEN_PARAMS" in os.environ:
        return json.loads(os.environ["GRAPHGEN_PARAMS"])

    # 方式2：配置文件
    if os.path.exists("/config/params.json"):
        with open("/config/params.json", "r") as f:
            return json.load(f)

    # 方式3：标准输入
    if not sys.stdin.isatty():
        return json.load(sys.stdin)

    raise Exception("No parameters provided. Set GRAPHGEN_PARAMS env var, mount /config/params.json, or pipe JSON to stdin.")

def get_partition_params(params):
    """根据分区方法提取对应参数（复用webui/app.py逻辑）"""
    method = params.get("partition_method", "ece")

    if method == "dfs":
        return {"max_units_per_community": params.get("dfs_max_units", 5)}
    elif method == "bfs":
        return {"max_units_per_community": params.get("bfs_max_units", 5)}
    elif method == "leiden":
        return {
            "max_size": params.get("leiden_max_size", 20),
            "use_lcc": params.get("leiden_use_lcc", False),
            "random_seed": params.get("leiden_random_seed", 42),
        }
    else:  # ece
        return {
            "max_units_per_community": params.get("ece_max_units", 20),
            "min_units_per_community": params.get("ece_min_units", 3),
            "max_tokens_per_community": params.get("ece_max_tokens", 10240),
            "unit_sampling": params.get("ece_unit_sampling", "random"),
        }

def build_config(params):
    """构建GraphGen YAML配置（复用webui/app.py逻辑）"""

    # 设置环境变量（LLM配置）
    os.environ["SYNTHESIZER_BACKEND"] = "openai_api"
    os.environ["SYNTHESIZER_MODEL"] = params["synthesizer_model"]
    os.environ["SYNTHESIZER_BASE_URL"] = params["synthesizer_url"]
    os.environ["SYNTHESIZER_API_KEY"] = params["api_key"]
    os.environ["TOKENIZER_MODEL"] = params.get("tokenizer", "cl100k_base")
    os.environ["RPM"] = str(params.get("rpm", 1000))
    os.environ["TPM"] = str(params.get("tpm", 50000))

    if params.get("if_trainee_model"):
        os.environ["TRAINEE_BACKEND"] = "openai_api"
        os.environ["TRAINEE_MODEL"] = params["trainee_model"]
        os.environ["TRAINEE_BASE_URL"] = params["trainee_url"]
        os.environ["TRAINEE_API_KEY"] = params["trainee_api_key"]

    # 构建节点列表（复用webui/app.py的DAG构建逻辑）
    nodes = [
        {
            "id": "read",
            "op_name": "read",
            "type": "source",
            "dependencies": [],
            "params": {"input_path": [params["upload_file"]]},
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

    # 可选：quiz和judge节点
    if params.get("if_trainee_model"):
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

    # Partition节点
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
    config = {
        "global_params": {
            "working_dir": OUTPUT_DIR,
            "graph_backend": "kuzu",
            "kv_backend": "rocksdb",
        },
        "nodes": nodes,
    }

    return config

def main():
    # 1. 读取参数
    params = load_params()
    print("Loaded parameters:")
    print(json.dumps(params, indent=2, ensure_ascii=False))

    # 2. 构建配置
    config = build_config(params)

    # 3. 写入YAML文件
    output_file = "/tmp/graphgen_config.yaml"
    with open(output_file, "w") as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True)

    print(f"\nGenerated config file: {output_file}")
    print("Config content:")
    with open(output_file, "r") as f:
        print(f.read())

if __name__ == "__main__":
    main()
