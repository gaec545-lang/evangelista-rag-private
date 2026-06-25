import os
from typing import Any
import structlog
from src.llm.base import LLMClient
from src.llm.config import get_model_config, LLMModelConfig
from src.config import settings

logger = structlog.get_logger()


class FallbackLLMClient(LLMClient):
    """
    ponytail: Fallback wrapper to route calls to alternative LLM providers
    if the primary client fails.
    """
    def __init__(self, primary: LLMClient, fallbacks: list[LLMClient]) -> None:
        self.primary = primary
        self.fallbacks = fallbacks

    @property
    def __class__(self):
        return self.primary.__class__

    def __getattr__(self, name: str) -> Any:
        return getattr(self.primary, name)

    async def generate(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = 0.3,
        max_tokens: int = 2000,
    ) -> str:
        clients = [self.primary] + self.fallbacks
        last_error = None
        for i, client in enumerate(clients):
            try:
                # ponytail: Attempt generation with current client
                return await client.generate(
                    prompt,
                    system_prompt=system_prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
            except Exception as e:
                last_error = e
                logger.warning(
                    "llm_client_failed_trying_fallback",
                    client_index=i,
                    client_class=client.__class__.__name__,
                    error=str(e),
                )
        
        logger.error("all_llm_clients_failed")
        raise RuntimeError(f"All configured LLM clients failed. Last error: {last_error}") from last_error

    async def embed(self, text: str) -> list[float]:
        # ponytail: Fallback embedding logic
        clients = [self.primary] + self.fallbacks
        last_error = None
        for i, client in enumerate(clients):
            try:
                return await client.embed(text)
            except Exception as e:
                last_error = e
                logger.warning(
                    "llm_embed_failed_trying_fallback",
                    client_index=i,
                    client_class=client.__class__.__name__,
                    error=str(e),
                )
        raise RuntimeError(f"All configured LLM clients failed to embed. Last error: {last_error}") from last_error


def _build_client_raw(name: str) -> Any:
    """Helper to build a raw client without wrapping it in FallbackLLMClient."""
    config = get_model_config(name)
    key = getattr(settings, config.api_key_env, "") or os.getenv(config.api_key_env)
    
    if config.provider == "openai_generic":
        from src.llm.providers.generic_openai import GenericOpenAIProvider
        return GenericOpenAIProvider(config)
    
    elif config.provider == "groq":
        from src.llm.groq_client import GroqClient
        model_id = settings.GROQ_MODEL or config.model_id
        return GroqClient(
            api_key=key,
            model=model_id,
            base_url=config.base_url or "https://api.groq.com/openai/v1"
        )
    
    elif config.provider == "ollama":
        from src.llm.ollama_client import OllamaClient
        model_id = settings.OLLAMA_MODEL or config.model_id
        return OllamaClient(
            base_url=config.base_url or settings.OLLAMA_BASE_URL,
            model=model_id
        )
    
    elif config.provider == "anthropic":
        from src.llm.anthropic_client import AnthropicClient
        model_id = settings.ANTHROPIC_MODEL or config.model_id
        return AnthropicClient(
            api_key=key,
            model=model_id,
            base_url=config.base_url or "https://api.anthropic.com"
        )
    
    else:
        logger.warning("unknown_provider_fallback", provider=config.provider)
        from src.llm.providers.generic_openai import GenericOpenAIProvider
        return GenericOpenAIProvider(config)


def _has_config(name: str) -> bool:
    """ponytail: Check if a model has valid keys or endpoints."""
    try:
        config = get_model_config(name)
        if config.provider == "ollama":
            return True
        if config.api_key_env == "NONE":
            return True
        key = getattr(settings, config.api_key_env, "") or os.getenv(config.api_key_env)
        return bool(key)
    except Exception:
        return False


_client_cache = {}


def get_llm_client(model_name: str | None = None) -> Any:
    """
    Retorna un cliente LLM dinámicamente basado en la configuración.
    Usa caché local y envuelve el cliente principal en FallbackLLMClient
    para garantizar resiliencia y alta disponibilidad.
    """
    name = model_name or settings.LLM_MODEL
    
    # ponytail: Return cached FallbackLLMClient to reuse connections & reduce overhead
    if name in _client_cache:
        return _client_cache[name]
        
    logger.info("creating_llm_client", model=name)
    primary = _build_client_raw(name)
    
    # ponytail: Define candidates for fallbacks (exclude the current model, include valid ones)
    candidates = ["groq-llama-70b", "anthropic-claude", "ollama-local"]
    fallbacks = []
    for cand in candidates:
        if cand != name and _has_config(cand):
            try:
                fallbacks.append(_build_client_raw(cand))
            except Exception as e:
                logger.warning("failed_to_instantiate_fallback", model=cand, error=str(e))
                
    client = FallbackLLMClient(primary, fallbacks)
    _client_cache[name] = client
    return client
