import json
from pathlib import Path
from typing import Any, List, Union

import pandas as pd

from graphgen.bases.base_reader import BaseReader
from graphgen.common.init_storage import init_storage
from graphgen.utils import compute_dict_hash


def _ensure_records(data: Any) -> list[dict]:
    if isinstance(data, dict):
        return [data]
    if isinstance(data, list):
        return data
    raise ValueError(f"Unsupported JSON payload type: {type(data)!r}")


def _validate_records(records: list[dict]) -> list[dict]:
    reader = BaseReader.__new__(BaseReader)
    reader.text_column = "content"
    reader.modalities = ["text"]

    batch = pd.DataFrame(records)
    batch = reader._validate_batch(batch)
    validated = batch.to_dict(orient="records")
    return [item for item in validated if reader._should_keep_item(item)]


def _read_text_with_fallback(source_path: str) -> str:
    encodings = ("utf-8", "utf-8-sig", "gb18030", "gbk", "latin-1")
    errors = []
    for encoding in encodings:
        try:
            with open(source_path, "r", encoding=encoding) as f:
                return f.read()
        except UnicodeDecodeError as exc:
            errors.append(f"{encoding}: {exc}")
    raise UnicodeDecodeError(
        "unknown",
        b"",
        0,
        1,
        "Unable to decode text file with supported encodings: "
        + "; ".join(errors),
    )


def local_read(
    input_path: Union[str, List[str]],
    working_dir: str = "cache",
    kv_backend: str = "json_kv",
) -> pd.DataFrame:
    paths = [input_path] if isinstance(input_path, str) else input_path
    if len(paths) != 1:
        raise ValueError(
            "Local runtime currently supports exactly one input file path."
        )

    source_path = str(Path(paths[0]).expanduser().resolve())
    suffix = Path(source_path).suffix.lower()

    if suffix in {".txt", ".md"}:
        records = [
            {
                "type": "text",
                "content": _read_text_with_fallback(source_path),
                "path": source_path,
            }
        ]
    elif suffix == ".jsonl":
        with open(source_path, "r", encoding="utf-8") as f:
            records = [json.loads(line) for line in f if line.strip()]
        for item in records:
            item["path"] = source_path
        records = _validate_records(records)
    elif suffix == ".json":
        with open(source_path, "r", encoding="utf-8") as f:
            records = _ensure_records(json.load(f))
        for item in records:
            if "content" in item and isinstance(item["content"], dict):
                item["content"] = json.dumps(item["content"], ensure_ascii=False)
            item["path"] = source_path
        records = _validate_records(records)
    elif suffix == ".csv":
        records = pd.read_csv(source_path).to_dict(orient="records")
        for item in records:
            item["path"] = source_path
        records = _validate_records(records)
    else:
        raise ValueError(
            f"Unsupported input suffix for local runtime: {suffix}. "
            "Supported: .txt, .md, .json, .jsonl, .csv"
        )

    for item in records:
        item["_trace_id"] = compute_dict_hash(item, prefix="read-")

    if records:
        read_storage = init_storage(
            backend=kv_backend, working_dir=working_dir, namespace="read"
        )
        read_storage.upsert({item["_trace_id"]: item for item in records})
        read_storage.index_done_callback()

    return pd.DataFrame(records)
