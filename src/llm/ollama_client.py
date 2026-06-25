"""Cliente LLM para Ollama (prod — modelos locales)."""
import asyncio
import httpx
from src.llm.base import LLMClient
from src.utils.logger import get_logger

logger = get_logger(__name__)

MAX_RETRIES = 3
RETRY_BACKOFF = 2.0


class OllamaClient(LLMClient):
    """
    Cliente para modelos locales via Ollama.
    Timeout extendido a 180s para modelos grandes como qwen2.5:32b.
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

        # ponytail: Reuse AsyncClient in a single block, handle timeouts (180s) and retries for busy/cold-started Ollama.
        async with httpx.AsyncClient(timeout=httpx.Timeout(180.0, connect=10.0)) as client:
            for attempt in range(MAX_RETRIES):
                try:
                    response = await client.post(f"{self.base_url}/api/generate", json=payload)
                    response.raise_for_status()
                    return response.json()["response"]
                except httpx.HTTPError as e:
                    if attempt == MAX_RETRIES - 1:
                        logger.error("error_ollama_generate_definitivo", model=self.model, error=str(e))
                        raise
                    wait = RETRY_BACKOFF * (2**attempt)
                    logger.warning("error_ollama_generate_retry", model=self.model, intento=attempt + 1, esperando=wait, error=str(e))
                    await asyncio.sleep(wait)

        raise RuntimeError("Ollama generate: máximo de reintentos excedido")

    async def embed(self, text: str) -> list[float]:
        """Genera embedding usando nomic-embed-text via Ollama."""
        # ponytail: Added retries and connection reuse for embedding requests.
        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=10.0)) as client:
            for attempt in range(MAX_RETRIES):
                try:
                    response = await client.post(
                        f"{self.base_url}/api/embeddings",
                        json={"model": self.embed_model, "prompt": text},
                    )
                    response.raise_for_status()
                    return response.json()["embedding"]
                except httpx.HTTPError as e:
                    if attempt == MAX_RETRIES - 1:
                        logger.error("error_ollama_embed_definitivo", error=str(e))
                        raise
                    wait = RETRY_BACKOFF * (2**attempt)
                    logger.warning("error_ollama_embed_retry", intento=attempt + 1, esperando=wait, error=str(e))
                    await asyncio.sleep(wait)

        raise RuntimeError("Ollama embed: máximo de reintentos excedido")
