import os
from typing import Any
import structlog
from src.llm.config import get_model_config, LLMModelConfig
from src.config import settings

logger = structlog.get_logger()

def get_llm_client(model_name: str | None = None) -> Any:
    """
    Retorna un cliente LLM dinámicamente basado en la configuración.
    Prioridad: 
    1. model_name pasado por parámetro.
    2. settings.LLM_MODEL (desde .env).
    3. Default definido en config.py.
    """
    name = model_name or settings.LLM_MODEL
    config = get_model_config(name)
    
    logger.info("creating_llm_client", model=name, provider=config.provider)

    if config.provider == "openai_generic":
        from src.llm.providers.generic_openai import GenericOpenAIProvider
        return GenericOpenAIProvider(config)
    
    elif config.provider == "groq":
        from src.llm.groq_client import GroqClient
        return GroqClient(
            api_key=os.getenv(config.api_key_env, settings.GROQ_API_KEY),
            model=config.model_id
        )
    
    elif config.provider == "ollama":
        from src.llm.ollama_client import OllamaClient
        return OllamaClient(
            base_url=config.base_url or settings.OLLAMA_BASE_URL,
            model=config.model_id
        )
    
    elif config.provider == "anthropic":
        from src.llm.anthropic_client import AnthropicClient
        return AnthropicClient(
            api_key=os.getenv(config.api_key_env, settings.ANTHROPIC_API_KEY),
            model=config.model_id
        )
    
    else:
        # Fallback a genérico si el provider no está mapeado explícitamente pero es compatible
        logger.warning("unknown_provider_fallback", provider=config.provider)
        from src.llm.providers.generic_openai import GenericOpenAIProvider
        return GenericOpenAIProvider(config)
