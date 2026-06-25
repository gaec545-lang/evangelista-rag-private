"""Cliente LLM para Groq API (dev - free tier)."""
import asyncio
import httpx
from src.llm.base import LLMClient
from src.ingestion.embedder import Embedder
from src.utils.logger import get_logger

logger = get_logger(__name__)

MAX_RETRIES = 5
RETRY_BACKOFF = 2.0  # ponytail: lowered from 4.0 to make transient retries faster


class GroqClient(LLMClient):
    """
    Cliente para Groq API usando Llama 3.3 70B.
    Incluye retry con backoff exponencial para el rate limit del free tier.
    Los embeddings se delegan a Ollama (Groq no tiene endpoint de embeddings).
    """

    def __init__(self, api_key: str, model: str, base_url: str = "https://api.groq.com/openai/v1") -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self._embedder = Embedder()
        # ponytail: reuse a single AsyncClient instance to prevent connection overhead and support connection pooling
        self._client = httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=10.0))

    async def generate(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = 0.3,
        max_tokens: int = 2000,
    ) -> str:
        """Genera texto con Groq API con reintentos automáticos."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        api_url = f"{self.base_url}/chat/completions"

        for attempt in range(MAX_RETRIES):
            try:
                response = await self._client.post(
                    api_url,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.model,
                        "messages": messages,
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                    },
                )
                
                if response.status_code == 429:
                    wait = RETRY_BACKOFF * (2**attempt)
                    logger.warning("rate_limit_groq", intento=attempt + 1, esperando=wait)
                    await asyncio.sleep(wait)
                    continue
                    
                response.raise_for_status()
                return response.json()["choices"][0]["message"]["content"]
                
            except httpx.HTTPError as e:
                # ponytail: Catch all HTTP errors (including ConnectTimeout, ReadTimeout) to retry properly.
                if attempt == MAX_RETRIES - 1:
                    logger.error("error_groq_definitivo", error=str(e))
                    raise
                wait = RETRY_BACKOFF * (2**attempt)
                logger.warning("error_groq_retry", intento=attempt + 1, esperando=wait, error=str(e))
                await asyncio.sleep(wait)

        raise RuntimeError("Groq API: máximo de reintentos excedido")

    async def embed(self, text: str) -> list[float]:
        """Delega embeddings a Ollama (Groq no tiene endpoint de embeddings)."""
        return await self._embedder.embed_single(text)
