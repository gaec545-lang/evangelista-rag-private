"""Cliente LLM para Anthropic Claude API (fallback)."""
from src.llm.base import LLMClient
from src.ingestion.embedder import Embedder
from src.utils.logger import get_logger

logger = get_logger(__name__)


class AnthropicClient(LLMClient):
    """
    Cliente para la API de Anthropic (Claude).
    Los embeddings se delegan a Ollama (Anthropic no tiene endpoint de embeddings).
    """

    def __init__(self, api_key: str, model: str, base_url: str = "https://api.anthropic.com") -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self._embedder = Embedder()
        try:
            import anthropic
            if not api_key:
                # ponytail: Avoid crashing during factory initialization if API key is missing
                self._client = None
            else:
                # ponytail: Set client-level timeouts and max_retries on client creation
                self._client = anthropic.AsyncAnthropic(
                    api_key=api_key,
                    base_url=self.base_url,
                    timeout=60.0,
                    max_retries=5
                )
        except ImportError:
            logger.warning("anthropic_sdk_no_instalado")
            self._client = None

    async def generate(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = 0.3,
        max_tokens: int = 2000,
    ) -> str:
        """Genera texto con Claude API."""
        if self._client is None:
            raise RuntimeError("SDK de Anthropic no instalado o API key faltante.")

        kwargs: dict = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
        }
        if system_prompt:
            kwargs["system"] = system_prompt

        try:
            message = await self._client.messages.create(**kwargs)
            return message.content[0].text
        except Exception as e:
            logger.error("error_anthropic_generate", model=self.model, error=str(e))
            raise

    async def embed(self, text: str) -> list[float]:
        """Delega embeddings a Ollama (Anthropic no tiene endpoint de embeddings)."""
        return await self._embedder.embed_single(text)
