import argparse
import os
import time
from importlib import resources

import ray
import yaml
from dotenv import load_dotenv

from graphgen.engine import Engine
from graphgen.operators import operators
from graphgen.utils import CURRENT_LOGGER_VAR, logger, set_logger

load_dotenv()

sys_path = os.path.abspath(os.path.dirname(__file__))

# Token usage logging file (set by entrypoint.sh)
# Note: Read at function call time, not module load time, to ensure Ray actors can access it


def log_token_usage(engine):
    """Log token usage statistics to the entrypoint log file."""
    # Read environment variable at function call time
    entrypoint_log_file = os.environ.get("ENTRYPOINT_LOG_FILE")
    if not entrypoint_log_file:
        logger.info("ENTRYPOINT_LOG_FILE not set, skipping token usage logging")
        return

    token_stats = {}
    for name, llm_proxy in engine.llm_actors.items():
        if llm_proxy is not None:
            try:
                usage = ray.get(llm_proxy.actor_handle.get_token_usage.remote())
                token_stats[name] = usage
            except Exception as e:
                logger.warning("Failed to get token usage for %s: %s", name, e)

    if not token_stats:
        return

    # Write to entrypoint log file
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(entrypoint_log_file, "a", encoding="utf-8") as f:
        f.write(f"\n[{timestamp}] [INFO] ==========================================\n")
        f.write(f"[{timestamp}] [INFO] Token Usage Statistics\n")
        f.write(f"[{timestamp}] [INFO] ==========================================\n")
        for name, stats in token_stats.items():
            f.write(f"[{timestamp}] [INFO] [{name.upper()}]\n")
            f.write(f"[{timestamp}] [INFO]   Total Requests: {stats['request_count']}\n")
            f.write(f"[{timestamp}] [INFO]   Total Prompt Tokens: {stats['total_prompt_tokens']}\n")
            f.write(f"[{timestamp}] [INFO]   Total Completion Tokens: {stats['total_completion_tokens']}\n")
            f.write(f"[{timestamp}] [INFO]   Total Tokens: {stats['total_tokens']}\n")
        f.write(f"[{timestamp}] [INFO] ==========================================\n")

    logger.info("Token usage statistics written to %s", entrypoint_log_file)


def set_working_dir(folder):
    os.makedirs(folder, exist_ok=True)


def save_config(config_path, global_config):
    if not os.path.exists(os.path.dirname(config_path)):
        os.makedirs(os.path.dirname(config_path))
    with open(config_path, "w", encoding="utf-8") as config_file:
        yaml.dump(
            global_config, config_file, default_flow_style=False, allow_unicode=True
        )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config_file",
        help="Config parameters for GraphGen.",
        default=resources.files("graphgen")
        .joinpath("configs")
        .joinpath("aggregated_config.yaml"),
        type=str,
    )

    args = parser.parse_args()

    with open(args.config_file, "r", encoding="utf-8") as f:
        config = yaml.load(f, Loader=yaml.FullLoader)

    working_dir = config.get("global_params", {}).get("working_dir", "cache")
    unique_id = int(time.time())
    output_path = os.path.join(working_dir, "output", f"{unique_id}")
    set_working_dir(output_path)
    log_path = os.path.join(working_dir, "logs", "Driver.log")
    driver_logger = set_logger(
        log_path,
        name="GraphGen",
        if_stream=True,
    )
    CURRENT_LOGGER_VAR.set(driver_logger)
    logger.info(
        "GraphGen with unique ID %s logging to %s",
        unique_id,
        log_path,
    )

    engine = Engine(config, operators)
    ds = ray.data.from_items([])
    engine.execute(ds, output_dir=output_path)

    save_config(os.path.join(output_path, "config.yaml"), config)
    logger.info("GraphGen completed successfully. Data saved to %s", output_path)

    # Output token usage statistics to entrypoint log file
    log_token_usage(engine)


if __name__ == "__main__":
    main()
