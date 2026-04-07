import json

import pandas as pd
import pytest

from graphgen.bases.datatypes import Node
from graphgen.local_engine import LocalEngine


class StreamingFailOperator:
    def __init__(self, **kwargs):
        pass

    def __call__(self, batch: pd.DataFrame):
        yield pd.DataFrame(
            [{"question": "q1", "answer": "a1", "_trace_id": "generated-1"}]
        )
        raise RuntimeError("stream interrupted")


def test_stream_output_persists_partial_results_on_failure(tmp_path):
    engine = object.__new__(LocalEngine)
    engine.global_params = {"working_dir": str(tmp_path), "kv_backend": "json_kv"}
    engine.functions = {"generate": StreamingFailOperator}
    engine.datasets = {
        "partition": pd.DataFrame(
            [{"_trace_id": "partition-1", "nodes": ["n1"], "edges": []}]
        )
    }

    node = Node(
        id="generate",
        op_name="generate",
        type="map_batch",
        dependencies=["partition"],
        execution_params={"batch_size": 1},
        save_output=True,
    )

    with pytest.raises(RuntimeError, match="stream interrupted"):
        engine._execute_node(node, pd.DataFrame(), output_dir=str(tmp_path))

    output_file = tmp_path / "generate" / "generate.jsonl"
    assert output_file.exists()

    lines = output_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0]) == {"question": "q1", "answer": "a1"}
