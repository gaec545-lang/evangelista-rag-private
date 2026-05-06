"""Tests para el módulo de embeddings."""
import pytest
from src.ingestion.embedder import Embedder, BATCH_SIZE


@pytest.fixture
def embedder():
    return Embedder(base_url="http://localhost:11434", model="nomic-embed-text")


class TestEmbedder:
    def test_embedder_init(self, embedder):
        """Verifica que el Embedder se inicializa con los parámetros correctos."""
        assert embedder.base_url == "http://localhost:11434"
        assert embedder.model == "nomic-embed-text"

    def test_batch_size_config(self):
        """Verifica la constante de batch size."""
        assert BATCH_SIZE > 0
        assert BATCH_SIZE <= 50

    def test_embedder_strips_trailing_slash(self):
        """Verifica que el base_url se normaliza correctamente."""
        e = Embedder(base_url="http://localhost:11434/", model="nomic-embed-text")
        assert not e.base_url.endswith("/")

    def test_embedder_default_model(self):
        """Verifica que el modelo por defecto se configura desde settings."""
        from src.config import settings
        e = Embedder()
        assert e.model == settings.EMBED_MODEL
        assert e.base_url == settings.OLLAMA_BASE_URL.rstrip("/")

    @pytest.mark.asyncio
    @pytest.mark.skipif(
        True,  # Siempre skip en CI — requiere Ollama corriendo
        reason="Requiere Ollama corriendo con nomic-embed-text instalado",
    )
    async def test_embed_single_real(self, embedder):
        """Test real que requiere Ollama. Se activa manualmente."""
        embedding = await embedder.embed_single("texto de prueba")
        assert len(embedding) == 768
        assert all(isinstance(x, float) for x in embedding)

    @pytest.mark.asyncio
    @pytest.mark.skipif(
        True,
        reason="Requiere Ollama corriendo con nomic-embed-text instalado",
    )
    async def test_health_check_real(self, embedder):
        """Verifica que Ollama está disponible y el modelo cargado."""
        available = await embedder.health_check()
        assert isinstance(available, bool)
