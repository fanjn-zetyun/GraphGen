import logging

from graphgen.operators.generate.generate_service import GenerateService
from graphgen.utils.log import CURRENT_LOGGER_VAR


class DummyGenerator:
    async def generate(self, triple):
        node_name = triple[0][0][0]
        return [{"question": f"q-{node_name}", "answer": f"a-{node_name}"}]

    @staticmethod
    def format_generation_results(result: dict, output_data_format: str) -> dict:
        assert output_data_format == "Alpaca"
        return {
            "instruction": result["question"],
            "input": "",
            "output": result["answer"],
        }


def test_generate_service_streams_results_per_input():
    service = object.__new__(GenerateService)
    service.method = "aggregated"
    service.data_format = "Alpaca"
    service.generator = DummyGenerator()
    service.get_trace_id = lambda content: f"trace-{content['instruction']}"
    logger_token = CURRENT_LOGGER_VAR.set(logging.getLogger("test-generate-stream"))

    batch = [
        {"_trace_id": "input-1", "nodes": [("n1", {})], "edges": []},
        {"_trace_id": "input-2", "nodes": [("n2", {})], "edges": []},
    ]

    try:
        stream, meta = service.process(batch)
        chunks = list(stream)
    finally:
        CURRENT_LOGGER_VAR.reset(logger_token)

    assert meta == {}
    assert len(chunks) == 2
    first_results, first_meta = chunks[0]
    second_results, second_meta = chunks[1]

    assert len(first_results) == 1
    assert len(second_results) == 1
    assert first_results[0]["instruction"] in {"q-n1", "q-n2"}
    assert second_results[0]["instruction"] in {"q-n1", "q-n2"}
    assert first_results[0]["instruction"] != second_results[0]["instruction"]
    assert list(first_meta.values())[0] == [first_results[0]["_trace_id"]]
    assert list(second_meta.values())[0] == [second_results[0]["_trace_id"]]
