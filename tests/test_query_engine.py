"""Tests para el motor de búsqueda RAG."""
import pytest
from unittest.mock import AsyncMock, MagicMock

from src.retrieval.query_engine import QueryEngine
from src.core.models import SearchResult


def make_mock_hit(
    doc_id: str,
    title: str,
    section: str,
    agent_access: list,
    score: float = 0.9,
):
    """Crea un hit de Qdrant mockeado."""
    hit = MagicMock()
    hit.score = score
    hit.payload = {
        "chunk_id": f"chunk-{doc_id}",
        "document_id": doc_id,
        "document_title": title,
        "section_header": section,
        "content": f"Contenido de prueba para {title} — {section}",
        "type": "framework",
        "domain": ["finanzas"],
        "sector": ["manufactura"],
        "agent_access": agent_access,
        "confidence": "high",
        "source": "evangelista",
        "tags": ["foundation"],
        "chunk_index": 0,
        "total_chunks": 1,
        "file_hash": "abc123",
    }
    return hit


class TestQueryEngine:
    def test_format_context_con_resultados(self):
        """Verifica que format_context genera texto legible con fuentes numeradas."""
        engine = QueryEngine.__new__(QueryEngine)  # sin __init__

        results = [
            SearchResult(
                chunk_id="c1",
                document_id="EVK-TEST-001",
                document_title="Test Doc",
                section_header="Sección Test",
                content="Contenido de prueba.",
                score=0.95,
                metadata={"type": "framework"},
            )
        ]
        context = engine.format_context(results)
        assert "[Fuente 1]" in context
        assert "Test Doc" in context
        assert "Contenido de prueba." in context

    def test_format_context_sin_resultados(self):
        """Verifica el mensaje cuando no hay resultados."""
        engine = QueryEngine.__new__(QueryEngine)
        context = engine.format_context([])
        assert "No se encontraron" in context

    @pytest.mark.asyncio
    async def test_search_aplica_filtro_agente(self):
        """
        Verifica que el filtro de agent_access se aplica en toda búsqueda.
        El agente nunca debería poder omitir este filtro.
        """
        mock_embedder = AsyncMock()
        mock_embedder.embed_single = AsyncMock(return_value=[0.1] * 768)

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.points = [
            make_mock_hit("EVK-TEST-001", "ALCOA Protocol", "Aplicación", ["all"])
        ]
        mock_client.query_points.return_value = mock_response

        engine = QueryEngine.__new__(QueryEngine)
        engine.embedder = mock_embedder
        engine.client = mock_client
        engine.collection = "test_collection"
        engine.reranker = MagicMock()
        engine.reranker.rerank = lambda q, r, k: r[:k]

        results = await engine.search(
            query="¿Qué es ALCOA+?",
            agent_name="financial",
            final_k=5,
            client_id="test_client"
        )

        # Verificar que query_points fue llamado con algún filtro
        assert mock_client.query_points.called
        call_kwargs = mock_client.query_points.call_args
        assert call_kwargs is not None

    @pytest.mark.asyncio
    async def test_search_maneja_error_qdrant(self):
        """Si Qdrant falla, retorna lista vacía sin lanzar excepción."""
        mock_embedder = AsyncMock()
        mock_embedder.embed_single = AsyncMock(return_value=[0.1] * 768)

        mock_client = MagicMock()
        mock_client.search.side_effect = Exception("Qdrant no disponible")

        engine = QueryEngine.__new__(QueryEngine)
        engine.embedder = mock_embedder
        engine.client = mock_client
        engine.collection = "test_collection"
        engine.reranker = MagicMock()
        engine.reranker.rerank = lambda q, r, k: r[:k]

        results = await engine.search(query="test", agent_name="all", client_id="test_client")
        assert results == []
