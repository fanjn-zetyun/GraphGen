from collections import defaultdict
import asyncio
import time
from typing import List

from graphgen.bases import BaseLLMWrapper
from graphgen.bases.base_llm_wrapper import ContentModerationError
from graphgen.bases.base_storage import BaseGraphStorage
from graphgen.bases.datatypes import Chunk
from graphgen.models import LightRAGKGBuilder
from graphgen.utils import logger, run_concurrent
from graphgen.utils.loop import create_event_loop
from tqdm.asyncio import tqdm as tqdm_async


def _preview_text(text: str, max_len: int = 300) -> str:
    sanitized = " ".join(text.split())
    if len(sanitized) <= max_len:
        return sanitized
    return f"{sanitized[:max_len]}..."


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
        try:
            nodes_data, edges_data = await kg_builder.extract(chunk)
        except ContentModerationError as e:
            logger.warning(
                "KG extraction skipped chunk %s due to content moderation: %s",
                chunk.id,
                e,
            )
            logger.warning(
                "Content moderation chunk preview for %s: %s",
                chunk.id,
                _preview_text(chunk.content),
            )
            raise
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

    async def _run_all():
        async def _worker(index: int, chunk: Chunk):
            try:
                res = await extract_with_logging(chunk)
                return index, res, None
            except Exception as e:  # pragma: no cover - backend/runtime dependent
                return index, None, e

        tasks = [asyncio.create_task(_worker(i, chunk)) for i, chunk in enumerate(chunks)]
        results = [None] * len(chunks)
        failed_chunk_reasons: dict[str, str] = {}
        pbar = tqdm_async(
            total=len(chunks),
            desc="[2/4]Extracting entities and relationships from chunks",
            unit="chunk",
        )

        for future in asyncio.as_completed(tasks):
            index, result, error = await future
            if error:
                failed_chunk_reasons[chunks[index].id] = (
                    "content_moderation"
                    if isinstance(error, ContentModerationError)
                    else "request_failure"
                )
                if isinstance(error, ContentModerationError):
                    logger.warning(
                        "KG extraction skipped chunk at index %s due to content moderation.",
                        index,
                    )
                else:
                    logger.exception("Task failed at index %s: %s", index, error)
            else:
                results[index] = result
            pbar.update(1)

        pbar.close()
        return results, failed_chunk_reasons

    loop = create_event_loop()
    try:
        results, failed_chunk_reasons = loop.run_until_complete(_run_all())
    finally:
        loop.close()

    successful_chunk_ids = [
        chunks[index].id for index, result in enumerate(results) if result is not None
    ]
    failed_chunk_ids = list(failed_chunk_reasons.keys())

    if failed_chunk_ids:
        logger.warning(
            "KG extraction exhausted retries for %d/%d chunks. Failed chunk ids: %s",
            len(failed_chunk_ids),
            len(chunks),
            failed_chunk_ids,
        )

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

    return nodes, edges, successful_chunk_ids, failed_chunk_ids, failed_chunk_reasons
