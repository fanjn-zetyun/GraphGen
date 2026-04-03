import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from graphgen.models.llm.api.openai_client import OpenAIClient


@pytest.fixture
def openai_client() -> OpenAIClient:
    with patch(
        "graphgen.models.llm.api.openai_client.AsyncOpenAI", autospec=True
    ) as async_openai_mock:
        client = OpenAIClient(
            model="gpt-4o-mini", api_key="test-key", base_url="https://example.com/v1"
        )
        client.tokenizer = MagicMock()
        client.tokenizer.encode = MagicMock(side_effect=lambda text: text.split())
        client.client = MagicMock()
        client.client.chat = MagicMock()
        client.client.chat.completions = MagicMock()
        client.client.chat.completions.create = AsyncMock(
            return_value=SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(
                            content="hello <think>hidden</think> world"
                        ),
                        logprobs=SimpleNamespace(
                            content=[
                                SimpleNamespace(
                                    token="A",
                                    logprob=0.0,
                                    top_logprobs=[SimpleNamespace(token="A", logprob=0.0)],
                                )
                            ]
                        ),
                    )
                ],
                usage=SimpleNamespace(
                    prompt_tokens=3, completion_tokens=2, total_tokens=5
                ),
            )
        )
        assert async_openai_mock.called
        yield client


def test_generate_answer_includes_request_source(openai_client: OpenAIClient):
    result = asyncio.run(openai_client.generate_answer("hello"))

    assert result == "hello  world"
    call = openai_client.client.chat.completions.create.call_args
    assert call.kwargs["model"] == "gpt-4o-mini"
    assert call.kwargs["request_source"] == "ONLINE_WEB"
    assert openai_client.token_usage[-1] == {
        "prompt_tokens": 3,
        "completion_tokens": 2,
        "total_tokens": 5,
    }


def test_generate_topk_per_token_includes_request_source(openai_client: OpenAIClient):
    asyncio.run(openai_client.generate_topk_per_token("hello"))

    call = openai_client.client.chat.completions.create.call_args
    assert call.kwargs["request_source"] == "ONLINE_WEB"
    assert call.kwargs["logprobs"] is True
    assert call.kwargs["top_logprobs"] == openai_client.topk_per_token
