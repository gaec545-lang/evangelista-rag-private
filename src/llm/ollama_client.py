"""Cliente LLM para Ollama (prod — modelos locales)."""
import httpx
from src.llm.base import LLMClient
from src.utils.logger import get_logger

logger = get_logger(__name__)


class OllamaClient(LLMClient):
    """
    Cliente para modelos locales via Ollama.
    Timeout extendido a 120s para modelos grandes como qwen2.5:32b.
    """

    def __init__(self, base_url: str, model: str, embed_model: str = "nomic-embed-text") -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.embed_model = embed_model

    async def generate(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = 0.3,
        max_tokens: int = 2000,
    ) -> str:
        """Genera texto con un modelo local de Ollama."""
        payload: dict = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }
        if system_prompt:
            payload["system"] = system_prompt

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(f"{self.base_url}/api/generate", json=payload)
                response.raise_for_status()
                return response.json()["response"]
        except httpx.HTTPError as e:
            logger.error("error_ollama_generate", model=self.model, error=str(e))
            raise

    async def embed(self, text: str) -> list[float]:
        """Genera embedding usando nomic-embed-text via Ollama."""
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.base_url}/api/embeddings",
                    json={"model": self.embed_model, "prompt": text},
                )
                response.raise_for_status()
                return response.json()["embedding"]
        except httpx.HTTPError as e:
            logger.error("error_ollama_embed", error=str(e))
            raise
