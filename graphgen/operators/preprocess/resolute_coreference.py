from typing import List

from graphgen.bases.datatypes import Chunk
from graphgen.common.init_llm import CONTENT_MODERATION_BLOCKED
from graphgen.models import OpenAIClient
from graphgen.templates import COREFERENCE_RESOLUTION_PROMPT
from graphgen.utils import detect_main_language, logger


async def resolute_coreference(
    llm_client: OpenAIClient, chunks: List[Chunk]
) -> List[Chunk]:
    """
    Resolute conference

    :param llm_client: LLM model
    :param chunks: List of chunks
    :return: List of chunks
    """

    if len(chunks) == 0:
        return chunks

    results = [chunks[0]]

    for _, chunk in enumerate(chunks[1:]):
        language = detect_main_language(chunk.content)
        result = await llm_client.generate_answer(
            COREFERENCE_RESOLUTION_PROMPT[language].format(
                reference=results[0].content, input_sentence=chunk.content
            )
        )
        if result == CONTENT_MODERATION_BLOCKED:
            logger.warning("Content moderation blocked coreference resolution for chunk %s", chunk.id)
            results.append(chunk)  # Keep original chunk if moderation blocked
        else:
            results.append(Chunk(id=chunk.id, content=result))

    return results
