import asyncio
from typing import Iterable, Tuple

from graphgen.bases import BaseKVStorage, BaseLLMWrapper, BaseOperator
from graphgen.common.init_llm import init_llm
from graphgen.common.init_storage import init_storage
from graphgen.utils import logger
from graphgen.utils.loop import create_event_loop
from tqdm import tqdm


class GenerateService(BaseOperator):
    """
    Generate question-answer pairs based on nodes and edges.
    """

    def __init__(
        self,
        working_dir: str = "cache",
        kv_backend: str = "rocksdb",
        method: str = "aggregated",
        data_format: str = "ChatML",
        **generate_kwargs,
    ):
        super().__init__(
            working_dir=working_dir, kv_backend=kv_backend, op_name="generate"
        )
        self.llm_client: BaseLLMWrapper = init_llm("synthesizer")
        self.generate_storage: BaseKVStorage = init_storage(
            backend=kv_backend, working_dir=working_dir, namespace="generate"
        )
        self.chunk_storage: BaseKVStorage = init_storage(
            backend=kv_backend, working_dir=working_dir, namespace="chunk"
        )

        self.method = method
        self.data_format = data_format

        if self.method == "atomic":
            from graphgen.models import AtomicGenerator

            self.generator = AtomicGenerator(self.llm_client)
        elif self.method == "aggregated":
            from graphgen.models import AggregatedGenerator

            self.generator = AggregatedGenerator(self.llm_client)
        elif self.method == "multi_hop":
            from graphgen.models import MultiHopGenerator

            self.generator = MultiHopGenerator(self.llm_client)
        elif self.method == "cot":
            from graphgen.models import CoTGenerator

            self.generator = CoTGenerator(self.llm_client)
        elif self.method == "vqa":
            from graphgen.models import VQAGenerator

            self.generator = VQAGenerator(self.llm_client)
        elif self.method == "multi_choice":
            from graphgen.models import MultiChoiceGenerator

            self.generator = MultiChoiceGenerator(
                self.llm_client,
                num_of_questions=generate_kwargs.get("num_of_questions", 5),
            )
        elif self.method == "multi_answer":
            from graphgen.models import MultiAnswerGenerator

            self.generator = MultiAnswerGenerator(
                self.llm_client,
                num_of_questions=generate_kwargs.get("num_of_questions", 3),
            )
        elif self.method == "fill_in_blank":
            from graphgen.models import FillInBlankGenerator

            self.generator = FillInBlankGenerator(
                self.llm_client,
                num_of_questions=generate_kwargs.get("num_of_questions", 5),
            )
        elif self.method == "true_false":
            from graphgen.models import TrueFalseGenerator

            self.generator = TrueFalseGenerator(
                self.llm_client,
                num_of_questions=generate_kwargs.get("num_of_questions", 5),
            )
        else:
            raise ValueError(f"Unsupported generation mode: {method}")

    def _format_results_for_trace(
        self, input_trace_id: str, qa_pairs: list[dict]
    ) -> tuple[list[dict], dict]:
        if not qa_pairs:
            return [], {}

        formatted_results = []
        output_trace_ids = []
        for qa_pair in qa_pairs:
            res = self.generator.format_generation_results(
                qa_pair, output_data_format=self.data_format
            )
            res["_trace_id"] = self.get_trace_id(res)
            formatted_results.append(res)
            output_trace_ids.append(res["_trace_id"])

        return formatted_results, {input_trace_id: output_trace_ids}

    def _stream_generate_results(
        self, batch: list
    ) -> Iterable[tuple[list[dict], dict]]:
        triples = [(item["nodes"], item["edges"]) for item in batch]
        input_trace_ids = [item["_trace_id"] for item in batch]
        chunk_meta_inverse = self.chunk_storage.get_by_id("_meta_inverse") or {}
        doc_ids_by_index = {
            index: self._get_document_ids_from_batch_item(item, chunk_meta_inverse)
            for index, item in enumerate(batch)
        }
        successful_doc_ids = set()
        failed_indices = set()

        async def _worker(index: int, triple: tuple):
            try:
                qa_pairs = await self.generator.generate(triple)
                return index, qa_pairs, None
            except Exception as e:  # pragma: no cover - logged and skipped
                return index, None, e

        loop = create_event_loop()
        tasks = [
            loop.create_task(_worker(index, triple))
            for index, triple in enumerate(triples)
        ]
        pending = set(tasks)
        pbar = tqdm(total=len(tasks), desc="Generating QAs", unit="batch")

        try:
            while pending:
                done, pending = loop.run_until_complete(
                    asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
                )
                for task in done:
                    index, qa_pairs, error = task.result()
                    if error:
                        failed_indices.add(index)
                        logger.exception(
                            "Task failed at index %s during generation for document ids %s: %s",
                            index,
                            sorted(doc_ids_by_index.get(index, set())),
                            error,
                        )
                    else:
                        successful_doc_ids.update(doc_ids_by_index.get(index, set()))
                        formatted_results, meta_update = self._format_results_for_trace(
                            input_trace_ids[index], qa_pairs or []
                        )
                        if formatted_results:
                            yield formatted_results, meta_update
                    pbar.update(1)

            failed_doc_ids = sorted(
                {
                    doc_id
                    for index in failed_indices
                    for doc_id in doc_ids_by_index.get(index, set())
                    if doc_id not in successful_doc_ids
                }
            )
            if failed_doc_ids:
                raise RuntimeError(
                    "数据集生成失败：以下文档的所有关联分块在大模型请求超时/重试 3 次后仍全部失败，任务终止。"
                    f" document_ids={failed_doc_ids}"
                )
            if failed_indices and not successful_doc_ids:
                failed_trace_ids = sorted(input_trace_ids[index] for index in failed_indices)
                raise RuntimeError(
                    "数据集生成失败：所有失败生成单元都已耗尽 3 次请求，但无法回溯所属文档。"
                    f" trace_ids={failed_trace_ids}"
                )
        finally:
            for task in pending:
                task.cancel()
            pbar.close()
            loop.close()

    @staticmethod
    def _get_document_ids_from_batch_item(
        item: dict, chunk_meta_inverse: dict[str, str]
    ) -> set[str]:
        chunk_ids = set()

        for node in item.get("nodes", []):
            if isinstance(node, (tuple, list)) and len(node) >= 2 and isinstance(
                node[1], dict
            ):
                source_id = node[1].get("source_id", "")
                chunk_ids.update(filter(None, str(source_id).split("<SEP>")))

        for edge in item.get("edges", []):
            if isinstance(edge, (tuple, list)) and len(edge) >= 3 and isinstance(
                edge[2], dict
            ):
                source_id = edge[2].get("source_id", "")
                chunk_ids.update(filter(None, str(source_id).split("<SEP>")))

        return {
            chunk_meta_inverse[chunk_id]
            for chunk_id in chunk_ids
            if chunk_id in chunk_meta_inverse
        }

    def process(self, batch: list) -> Tuple[Iterable[tuple[list[dict], dict]], dict]:
        """
        Generate question-answer pairs based on nodes and edges.
        """
        logger.info("[Generation] mode: %s, batches: %d", self.method, len(batch))
        return self._stream_generate_results(batch), {}
