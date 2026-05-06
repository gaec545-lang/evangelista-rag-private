"""Generación de embeddings usando FastEmbed (local) u Ollama."""
import asyncio
import httpx
from typing import Optional, Any
from src.utils.logger import get_logger
from src.config import settings

logger = get_logger(__name__)

BATCH_SIZE = 10


class Embedder:
    """Genera embeddings usando FastEmbed (local) o el modelo nomic-embed-text via Ollama."""

    def __init__(
        self,
        provider: str = settings.EMBED_PROVIDER,
        model: str = settings.EMBED_MODEL,
        base_url: str = settings.OLLAMA_BASE_URL,
    ) -> None:
        self.provider = provider
        self.model = model
        self.base_url = base_url.rstrip("/")
        self._fastembed_model: Any = None

    @property
    def fastembed_model(self):
        if self.provider == "fastembed" and self._fastembed_model is None:
            try:
                from fastembed import TextEmbedding
                self._fastembed_model = TextEmbedding(model_name=self.model)
                logger.info("fastembed_inicializado", model=self.model)
            except Exception as e:
                logger.error("error_inicializando_fastembed", error=str(e))
                self.provider = "ollama"
        return self._fastembed_model

    async def embed_single(self, text: str) -> list[float]:
        """Genera el embedding de un texto individual."""
        model = self.fastembed_model
        if self.provider == "fastembed" and model:
            # FastEmbed.embed devuelve un iterador de numpy arrays
            embeddings = list(model.embed([text]))
            return embeddings[0].tolist()

        # Fallback a Ollama
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.base_url}/api/embeddings",
                    json={"model": self.model, "prompt": text},
                )
                response.raise_for_status()
                return response.json()["embedding"]
        except httpx.HTTPError as e:
            logger.error("error_embedding", model=self.model, error=str(e))
            raise

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Genera embeddings para un lote de textos."""
        if self.provider == "fastembed" and self._fastembed_model:
            embeddings = list(self._fastembed_model.embed(texts))
            return [e.tolist() for e in embeddings]

        # Fallback a Ollama en batches
        results: list[list[float]] = []
        for i in range(0, len(texts), BATCH_SIZE):
            batch = texts[i : i + BATCH_SIZE]
            batch_results = []
            for text in batch:
                emb = await self.embed_single(text)
                batch_results.append(emb)
            results.extend(batch_results)
            if i + BATCH_SIZE < len(texts):
                await asyncio.sleep(0.1)

        logger.info("batch_embeddings_generados", total=len(results), model=self.model)
        return results

    async def health_check(self) -> bool:
        """Verifica que el proveedor de embeddings esté listo."""
        if self.provider == "fastembed":
            return self._fastembed_model is not None
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                response.raise_for_status()
                models = [m["name"] for m in response.json().get("models", [])]
                return any(self.model in m for m in models)
        except Exception as e:
            logger.error("error_health_check_embeddings", error=str(e))
            return False
