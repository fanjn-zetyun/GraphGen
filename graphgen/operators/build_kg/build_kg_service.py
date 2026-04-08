from typing import Tuple

from graphgen.bases import BaseGraphStorage, BaseLLMWrapper, BaseOperator
from graphgen.bases.datatypes import Chunk
from graphgen.common.init_llm import init_llm
from graphgen.common.init_storage import init_storage
from graphgen.utils import logger

from .build_mm_kg import build_mm_kg
from .build_text_kg import build_text_kg


class BuildKGService(BaseOperator):
    def __init__(
        self,
        working_dir: str = "cache",
        kv_backend: str = "rocksdb",
        graph_backend: str = "kuzu",
        **build_kwargs
    ):
        super().__init__(
            working_dir=working_dir, kv_backend=kv_backend, op_name="build_kg"
        )
        self.llm_client: BaseLLMWrapper = init_llm("synthesizer")
        self.graph_storage: BaseGraphStorage = init_storage(
            backend=graph_backend, working_dir=working_dir, namespace="graph"
        )
        self.chunk_storage = init_storage(
            backend=kv_backend, working_dir=working_dir, namespace="chunk"
        )
        self.build_kwargs = build_kwargs
        self.max_loop: int = int(self.build_kwargs.get("max_loop", 3))

    def _raise_if_documents_fully_failed(
        self,
        successful_chunk_ids: list[str],
        failed_chunk_ids: list[str],
        failed_chunk_reasons: dict[str, str],
    ) -> None:
        if not failed_chunk_ids:
            return

        chunk_meta_inverse = self.chunk_storage.get_by_id("_meta_inverse") or {}
        successful_doc_ids = {
            chunk_meta_inverse[chunk_id]
            for chunk_id in successful_chunk_ids
            if chunk_id in chunk_meta_inverse
        }
        failed_doc_ids = {
            chunk_meta_inverse[chunk_id]
            for chunk_id in failed_chunk_ids
            if chunk_id in chunk_meta_inverse
            and chunk_meta_inverse[chunk_id] not in successful_doc_ids
        }
        if not failed_doc_ids:
            if failed_chunk_ids and not successful_chunk_ids:
                raise RuntimeError(
                    "知识图谱抽取失败：所有失败分块都已耗尽 3 次请求，但无法回溯所属文档。"
                    f" chunk_ids={sorted(failed_chunk_ids)}"
                )
            return

        doc_reason_sets: dict[str, set[str]] = {}
        for chunk_id in failed_chunk_ids:
            doc_id = chunk_meta_inverse.get(chunk_id)
            if not doc_id or doc_id in successful_doc_ids:
                continue
            doc_reason_sets.setdefault(doc_id, set()).add(
                failed_chunk_reasons.get(chunk_id, "request_failure")
            )

        moderation_only_docs = sorted(
            doc_id
            for doc_id, reasons in doc_reason_sets.items()
            if reasons == {"content_moderation"}
        )
        request_only_docs = sorted(
            doc_id
            for doc_id, reasons in doc_reason_sets.items()
            if reasons == {"request_failure"}
        )
        mixed_docs = sorted(
            doc_id
            for doc_id, reasons in doc_reason_sets.items()
            if len(reasons) > 1
        )

        if sorted(failed_doc_ids) == moderation_only_docs:
            raise RuntimeError(
                "知识图谱抽取失败：以下文档的所有文本分块均因内容审核未通过，任务终止。"
                f" document_ids={moderation_only_docs}"
            )
        if sorted(failed_doc_ids) == request_only_docs:
            raise RuntimeError(
                "知识图谱抽取失败：以下文档的所有文本分块均因请求失败且重试耗尽，任务终止。"
                f" document_ids={request_only_docs}"
            )

        raise RuntimeError(
            "知识图谱抽取失败：以下文档的所有文本分块均未成功，其中同时包含请求失败和内容审核未通过，任务终止。"
            f" document_ids={sorted(mixed_docs or failed_doc_ids)}"
        )

    def process(self, batch: list) -> Tuple[list, dict]:
        """
        Build knowledge graph (KG) and merge into kg_instance
        :return: A tuple of (results, meta_updates)
            results: A list of dicts containing nodes and edges added to the KG. Each dict has the structure:
                {"_trace_id": str, "node": dict, "edge": dict}
            meta_updates: A dict mapping source IDs to lists of trace IDs for nodes and edges added.
        """
        chunks = [Chunk.from_dict(doc["_trace_id"], doc) for doc in batch]
        text_chunks = [chunk for chunk in chunks if chunk.type == "text"]
        mm_chunks = [
            chunk
            for chunk in chunks
            if chunk.type in ("image", "video", "table", "formula")
        ]

        logger.info(
            "Build KG batch received %d chunks: %d text, %d multi-modal",
            len(chunks),
            len(text_chunks),
            len(mm_chunks),
        )

        nodes = []
        edges = []

        if len(text_chunks) == 0:
            logger.info("All text chunks are already in the storage")
        else:
            logger.info(
                "[Text Entity and Relation Extraction] starting for %d text chunks",
                len(text_chunks),
            )
            (
                text_nodes,
                text_edges,
                successful_chunk_ids,
                failed_chunk_ids,
                failed_chunk_reasons,
            ) = build_text_kg(
                llm_client=self.llm_client,
                kg_instance=self.graph_storage,
                chunks=text_chunks,
                max_loop=self.max_loop,
            )
            self._raise_if_documents_fully_failed(
                successful_chunk_ids, failed_chunk_ids, failed_chunk_reasons
            )
            logger.info(
                "[Text Entity and Relation Extraction] completed with %d merged nodes and %d merged edges",
                len(text_nodes),
                len(text_edges),
            )
            nodes += text_nodes
            edges += text_edges
        if len(mm_chunks) == 0:
            logger.info("All multi-modal chunks are already in the storage")
        else:
            logger.info("[Multi-modal Entity and Relation Extraction] processing ...")
            mm_nodes, mm_edges = build_mm_kg(
                llm_client=self.llm_client,
                kg_instance=self.graph_storage,
                chunks=mm_chunks,
            )
            nodes += mm_nodes
            edges += mm_edges

        logger.info(
            "Writing KG index updates for %d nodes and %d edges", len(nodes), len(edges)
        )
        self.graph_storage.index_done_callback()
        logger.info("Knowledge graph building completed.")

        meta_updates = {}
        results = []
        for node in nodes:
            if not node:
                continue
            trace_id = node["entity_name"]
            results.append(
                {
                    "_trace_id": trace_id,
                    "node": node,
                    "edge": {},
                }
            )
            source_ids = node.get("source_id", "").split("<SEP>")
            for source_id in source_ids:
                meta_updates.setdefault(source_id, []).append(trace_id)
        for edge in edges:
            if not edge:
                continue
            trace_id = frozenset((edge["src_id"], edge["tgt_id"]))
            results.append(
                {
                    "_trace_id": str(trace_id),
                    "node": {},
                    "edge": edge,
                }
            )
            source_ids = edge.get("source_id", "").split("<SEP>")
            for source_id in source_ids:
                meta_updates.setdefault(source_id, []).append(str(trace_id))
        return results, meta_updates
