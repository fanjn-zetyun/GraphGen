import argparse
import json
import os
import time

import pandas as pd
import yaml
from dotenv import load_dotenv

from graphgen.local_engine import LocalEngine
from graphgen.operators import operators
from graphgen.utils import CURRENT_LOGGER_VAR, logger, set_logger

load_dotenv()


def set_working_dir(folder):
    os.makedirs(folder, exist_ok=True)


def save_config(config_path, global_config):
    if not os.path.exists(os.path.dirname(config_path)):
        os.makedirs(os.path.dirname(config_path))
    with open(config_path, "w", encoding="utf-8") as config_file:
        yaml.dump(
            global_config, config_file, default_flow_style=False, allow_unicode=True
        )


def build_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config_file", required=True, type=str)
    parser.add_argument("--input_path", type=str, default=None)
    parser.add_argument("--working_dir", type=str, default=None)
    parser.add_argument("--kv_backend", type=str, default="json_kv")
    parser.add_argument("--graph_backend", type=str, default="networkx")
    return parser


def apply_local_overrides(config, args):
    global_params = config.setdefault("global_params", {})
    global_params["kv_backend"] = args.kv_backend or global_params.get("kv_backend", "json_kv")
    global_params["graph_backend"] = args.graph_backend or global_params.get(
        "graph_backend", "networkx"
    )
    if args.working_dir:
        global_params["working_dir"] = args.working_dir
    else:
        global_params.setdefault("working_dir", "cache")

    if args.input_path:
        for node in config.get("nodes", []):
            if node.get("op_name") == "read":
                params = node.setdefault("params", {})
                params["input_path"] = [args.input_path]
                break

    return config


def apply_graphgen_params_env():
    graphgen_params = os.environ.get("GRAPHGEN_PARAMS")
    if not graphgen_params:
        return

    params = json.loads(graphgen_params)
    os.environ.setdefault("SYNTHESIZER_BACKEND", "openai_api")
    os.environ.setdefault(
        "SYNTHESIZER_MODEL",
        params.get("model_name") or params.get("synthesizer_model", ""),
    )
    os.environ.setdefault(
        "SYNTHESIZER_BASE_URL",
        params.get("base_url") or params.get("synthesizer_url", ""),
    )
    os.environ.setdefault("SYNTHESIZER_API_KEY", params.get("api_key", ""))
    os.environ.setdefault("TOKENIZER_MODEL", params.get("tokenizer", "cl100k_base"))
    os.environ.setdefault("RPM", str(params.get("rpm", 1000)))
    os.environ.setdefault("TPM", str(params.get("tpm", 50000)))


def main():
    parser = build_parser()
    args = parser.parse_args()

    os.environ["GRAPHGEN_RUNTIME"] = "local"
    apply_graphgen_params_env()

    with open(args.config_file, "r", encoding="utf-8") as f:
        config = yaml.load(f, Loader=yaml.FullLoader)

    config = apply_local_overrides(config, args)

    working_dir = config.get("global_params", {}).get("working_dir", "cache")
    unique_id = int(time.time())
    output_path = os.path.join(working_dir, "output", f"{unique_id}")
    set_working_dir(output_path)
    log_path = os.path.join(working_dir, "logs", "Driver.local.log")
    driver_logger = set_logger(
        log_path,
        name="GraphGenLocal",
        if_stream=True,
    )
    CURRENT_LOGGER_VAR.set(driver_logger)
    logger.info(
        "GraphGen local runtime with unique ID %s logging to %s",
        unique_id,
        log_path,
    )

    engine = LocalEngine(config, operators)
    engine.execute(pd.DataFrame(), output_dir=output_path)

    save_config(os.path.join(output_path, "config.yaml"), config)
    logger.info("GraphGen local runtime completed successfully. Data saved to %s", output_path)


if __name__ == "__main__":
    main()
