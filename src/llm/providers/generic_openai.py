import os
from typing import Optional, Dict, Any
import structlog
from src.llm.base import LLMClient
from src.llm.config import LLMModelConfig
from src.ingestion.embedder import Embedder
from src.config import settings

logger = structlog.get_logger()


class GenericOpenAIProvider(LLMClient):
    """Proveedor genérico para cualquier API compatible con OpenAI (SambaNova, Together, Cerebras, etc.)."""
    
    def __init__(self, config: LLMModelConfig):
        self.config = config
        # ponytail: Check settings first (for Azure Key Vault secrets) then fallback to env var
        api_key = getattr(settings, config.api_key_env, "") or os.getenv(config.api_key_env)
        
        if not api_key and config.api_key_env != "NONE":
            logger.warning("missing_api_key", env_var=config.api_key_env, model=config.name)
            # Intentar usar una genérica si no hay específica
            api_key = os.getenv("OPENAI_API_KEY", "no-key")

        if not api_key:
            api_key = "none"

        from openai import AsyncOpenAI
        # ponytail: Configured timeout and max_retries at AsyncOpenAI client level to avoid connection timeout failures
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=config.base_url,
            timeout=60.0,
            max_retries=5
        )
        self._embedder = Embedder()

    async def generate(self, prompt: str, system_prompt: str, **kwargs) -> str:
        """Genera una respuesta usando el cliente de OpenAI."""
        try:
            logger.info("llm_generation_start", model=self.config.name, provider=self.config.provider)
            
            # Combinar parámetros (config < kwargs)
            temperature = kwargs.get("temperature", self.config.temperature)
            max_tokens = kwargs.get("max_tokens", self.config.max_tokens)
            
            response = await self.client.chat.completions.create(
                model=self.config.model_id,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                temperature=temperature,
                max_tokens=max_tokens,
                **self.config.extra_params
            )
            
            content = response.choices[0].message.content
            logger.info("llm_generation_success", model=self.config.name, tokens=response.usage.total_tokens)
            return content or ""
            
        except Exception as e:
            logger.error("llm_generation_failed", model=self.config.name, error=str(e))
            return f"Error en generación con {self.config.name}: {str(e)}"

    async def embed(self, text: str) -> list[float]:
        """Delega embeddings a Ollama (o FastEmbed)."""
        return await self._embedder.embed_single(text)
