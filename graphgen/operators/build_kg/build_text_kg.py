from collections import defaultdict
import os
import time
from typing import List

from graphgen.bases import BaseLLMWrapper
from graphgen.bases.base_storage import BaseGraphStorage
from graphgen.bases.datatypes import Chunk
from graphgen.models import LightRAGKGBuilder
from graphgen.utils import logger, run_concurrent


def build_text_kg(
    llm_client: BaseLLMWrapper,
    kg_instance: BaseGraphStorage,
    chunks: List[Chunk],
    max_loop: int = 3,
) -> tuple:
    """
    :param llm_client: Synthesizer LLM model to extract entities and relationships
    :param kg_instance
    :param chunks
    :param max_loop: Maximum number of loops for entity and relationship extraction
    :return:
    """

    kg_builder = LightRAGKGBuilder(llm_client=llm_client, max_loop=max_loop)
    total_chunks = len(chunks)
    completed_chunks = 0

    async def extract_with_logging(chunk: Chunk):
        nonlocal completed_chunks
        started_at = time.monotonic()
        logger.info(
            "Starting KG extraction for chunk %s (%d chars)",
            chunk.id,
            len(chunk.content),
        )
        nodes_data, edges_data = await kg_builder.extract(chunk)
        completed_chunks += 1
        elapsed = time.monotonic() - started_at
        logger.info(
            "Finished KG extraction for chunk %s in %.1fs (%d/%d complete, %d node groups, %d edge groups)",
            chunk.id,
            elapsed,
            completed_chunks,
            total_chunks,
            len(nodes_data),
            len(edges_data),
        )
        return nodes_data, edges_data

    try:
        results = run_concurrent(
            extract_with_logging,
            chunks,
            desc="[2/4]Extracting entities and relationships from chunks",
            unit="chunk",
            raise_on_error=True,
            error_context="KG extraction",
        )
    except RuntimeError as exc:
        synthesizer_base_url = os.getenv("SYNTHESIZER_BASE_URL", "")
        synthesizer_api_key = os.getenv("SYNTHESIZER_API_KEY", "")
        synthesizer_model = os.getenv("SYNTHESIZER_MODEL", "")
        raise RuntimeError(
            "知识图谱抽取失败：无法完成大模型实体关系抽取。"
            "请检查模型服务可用性以及网络连通性。"
            f" 当前配置: SYNTHESIZER_MODEL={synthesizer_model or '<empty>'},"
            f" SYNTHESIZER_BASE_URL={synthesizer_base_url or '<empty>'},"
            f" SYNTHESIZER_API_KEY={synthesizer_api_key or '<empty>'}。"
            f" 原始错误：{exc}"
        ) from exc
    results = [res for res in results if res]
    logger.info(
        "Merging KG extraction results from %d completed chunks", len(results)
    )

    nodes = defaultdict(list)
    edges = defaultdict(list)
    for n, e in results:
        for k, v in n.items():
            nodes[k].extend(v)
        for k, v in e.items():
            edges[tuple(sorted(k))].extend(v)

    nodes = run_concurrent(
        lambda kv: kg_builder.merge_nodes(kv, kg_instance=kg_instance),
        list(nodes.items()),
        desc="Inserting entities into storage",
    )
    logger.info("Entity merge completed for %d entity groups", len(nodes))

    edges = run_concurrent(
        lambda kv: kg_builder.merge_edges(kv, kg_instance=kg_instance),
        list(edges.items()),
        desc="Inserting relationships into storage",
    )
    logger.info("Relationship merge completed for %d edge groups", len(edges))

    return nodes, edges
