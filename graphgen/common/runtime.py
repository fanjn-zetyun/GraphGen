import os


def use_local_runtime() -> bool:
    runtime = os.getenv("GRAPHGEN_RUNTIME", "").strip().lower()
    return runtime in {"local", "no_ray", "noray"}
