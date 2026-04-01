import logging
import os
from typing import TYPE_CHECKING, Any, Dict, Optional

from graphgen.bases import BaseLLMWrapper
from graphgen.common.runtime import use_local_runtime
from graphgen.models import Tokenizer

if TYPE_CHECKING:
    import ray

logger = logging.getLogger(__name__)

# 特殊标记，表示内容被审核拦截
CONTENT_MODERATION_BLOCKED = "[CONTENT_MODERATION_BLOCKED]"

_LOCAL_LLM_CACHE: dict[str, BaseLLMWrapper] = {}


def _build_llm_instance(backend: str, config: Dict[str, Any]):
    tokenizer_model = os.environ.get("TOKENIZER_MODEL", "cl100k_base")
    tokenizer = Tokenizer(model_name=tokenizer_model)
    config = dict(config)
    config["tokenizer"] = tokenizer

    if backend == "http_api":
        from graphgen.models.llm.api.http_client import HTTPClient

        return HTTPClient(**config)
    if backend in ("openai_api", "azure_openai_api"):
        from graphgen.models.llm.api.openai_client import OpenAIClient

        return OpenAIClient(**config, backend=backend)
    if backend == "ollama_api":
        from graphgen.models.llm.api.ollama_client import OllamaClient

        return OllamaClient(**config)
    if backend == "huggingface":
        from graphgen.models.llm.local.hf_wrapper import HuggingFaceWrapper

        return HuggingFaceWrapper(**config)
    if backend == "sglang":
        from graphgen.models.llm.local.sglang_wrapper import SGLangWrapper

        return SGLangWrapper(**config)
    if backend == "vllm":
        from graphgen.models.llm.local.vllm_wrapper import VLLMWrapper

        return VLLMWrapper(**config)
    raise NotImplementedError(f"Backend {backend} is not implemented yet.")


class LLMServiceActor:
    """
    A Ray actor class to wrap LLM wrapper instances for distributed usage.
    """

    def __init__(self, backend: str, config: Dict[str, Any]):
        self.backend = backend
        self.llm_instance = _build_llm_instance(backend, config)

    async def generate_answer(
        self, text: str, history: Optional[list[str]] = None, **extra: Any
    ) -> str:
        from graphgen.models.llm.api.openai_client import ContentModerationError
        try:
            return await self.llm_instance.generate_answer(text, history, **extra)
        except ContentModerationError as e:
            logger.warning("Content moderation blocked request: %s", str(e))
            return CONTENT_MODERATION_BLOCKED

    async def generate_topk_per_token(
        self, text: str, history: Optional[list[str]] = None, **extra: Any
    ) -> list:
        return await self.llm_instance.generate_topk_per_token(text, history, **extra)

    async def generate_inputs_prob(
        self, text: str, history: Optional[list[str]] = None, **extra: Any
    ) -> list:
        return await self.llm_instance.generate_inputs_prob(text, history, **extra)

    def ready(self) -> bool:
        """A simple method to check if the actor is ready."""
        return True

    def get_token_usage(self) -> Dict[str, Any]:
        """Get the token usage statistics from the LLM instance."""
        if hasattr(self.llm_instance, "token_usage"):
            return {
                "usage_records": self.llm_instance.token_usage,
                "total_prompt_tokens": sum(
                    u.get("prompt_tokens", 0) for u in self.llm_instance.token_usage
                ),
                "total_completion_tokens": sum(
                    u.get("completion_tokens", 0) for u in self.llm_instance.token_usage
                ),
                "total_tokens": sum(
                    u.get("total_tokens", 0) for u in self.llm_instance.token_usage
                ),
                "request_count": len(self.llm_instance.token_usage),
            }
        return {"usage_records": [], "total_prompt_tokens": 0, "total_completion_tokens": 0, "total_tokens": 0, "request_count": 0}


class LLMServiceProxy(BaseLLMWrapper):
    """
    A proxy class to interact with the LLMServiceActor for distributed LLM operations.
    """

    def __init__(self, actor_handle: "ray.actor.ActorHandle"):
        super().__init__()
        self.actor_handle = actor_handle
        self._create_local_tokenizer()

    async def generate_answer(
        self, text: str, history: Optional[list[str]] = None, **extra: Any
    ) -> str:
        object_ref = self.actor_handle.generate_answer.remote(text, history, **extra)
        return await object_ref

    async def generate_topk_per_token(
        self, text: str, history: Optional[list[str]] = None, **extra: Any
    ) -> list:
        object_ref = self.actor_handle.generate_topk_per_token.remote(
            text, history, **extra
        )
        return await object_ref

    async def generate_inputs_prob(
        self, text: str, history: Optional[list[str]] = None, **extra: Any
    ) -> list:
        object_ref = self.actor_handle.generate_inputs_prob.remote(
            text, history, **extra
        )
        return await object_ref

    def _create_local_tokenizer(self):
        tokenizer_model = os.environ.get("TOKENIZER_MODEL", "cl100k_base")
        self.tokenizer = Tokenizer(model_name=tokenizer_model)


class LLMFactory:
    """
    A factory class to create LLM wrapper instances based on the specified backend.
    Supported backends include:
    - http_api: HTTPClient
    - openai_api: OpenAIClient
    - ollama_api: OllamaClient
    - huggingface: HuggingFaceWrapper
    - sglang: SGLangWrapper
    """

    @staticmethod
    def create_llm(
        model_type: str, backend: str, config: Dict[str, Any]
    ) -> BaseLLMWrapper:
        import ray

        if not config:
            raise ValueError(
                f"No configuration provided for LLM {model_type} with backend {backend}."
            )

        actor_name = f"Actor_LLM_{model_type}"
        try:
            actor_handle = ray.get_actor(actor_name)
            print(f"Using existing Ray actor: {actor_name}")
        except ValueError:
            print(f"Creating Ray actor for LLM {model_type} with backend {backend}.")
            num_gpus = float(config.pop("num_gpus", 0))
            actor_handle = (
                ray.remote(LLMServiceActor)
                .options(
                    name=actor_name,
                    num_gpus=num_gpus,
                    get_if_exists=True,
                )
                .remote(backend, config)
            )

            # wait for actor to be ready
            ray.get(actor_handle.ready.remote())

        return LLMServiceProxy(actor_handle)


def _load_env_group(prefix: str) -> Dict[str, Any]:
    """
    Collect environment variables with the given prefix into a dictionary,
    stripping the prefix from the keys.
    """
    return {
        k[len(prefix) :].lower(): v
        for k, v in os.environ.items()
        if k.startswith(prefix)
    }


def init_llm(model_type: str) -> Optional[BaseLLMWrapper]:
    if model_type == "synthesizer":
        prefix = "SYNTHESIZER_"
    elif model_type == "trainee":
        prefix = "TRAINEE_"
    else:
        raise NotImplementedError(f"Model type {model_type} is not implemented yet.")
    config = _load_env_group(prefix)
    # if config is empty, return None
    if not config:
        return None
    backend = config.pop("backend")
    if use_local_runtime():
        cache_key = f"{model_type}:{backend}:{tuple(sorted(config.items()))}"
        if cache_key not in _LOCAL_LLM_CACHE:
            _LOCAL_LLM_CACHE[cache_key] = _build_llm_instance(backend, config)
        return _LOCAL_LLM_CACHE[cache_key]
    llm_wrapper = LLMFactory.create_llm(model_type, backend, config)
    return llm_wrapper
