"""Tests para el nuevo pipeline RAG (v2.2)."""
import pytest
from unittest.mock import AsyncMock, MagicMock

from src.retrieval.query_classifier import QueryClassifier, QueryClassification
from src.retrieval.corrective_evaluator import CorrectivenessEvaluator, EvaluationResult
from src.retrieval.hybrid_retriever import HybridRetriever, RetrievedChunk
from src.retrieval.query_engine import QueryEngine, OrchestratedResult
from src.core.models import SearchResult


@pytest.mark.asyncio
async def test_query_classifier_keywords():
    """Test 1: QueryClassifier — keywords exactos"""
    classifier = QueryClassifier()
    classifier.CONFIDENCE_THRESHOLD = 0.1  # bajar umbral para test sin fallback LLM
    # Para evitar llamar al LLM en el test, comprobamos solo los keywords que dan alta confianza
    # "cómo estructurar" (PROCEDURAL)
    res_proc = await classifier.classify("¿Cómo estructuro un issue tree?")
    assert res_proc.query_type == "PROCEDURAL"

    # "qué es" (FACTUAL)
    res_fac = await classifier.classify("¿Qué es el COI?")
    assert res_fac.query_type == "FACTUAL"

    # "aplicar" (METODOLOGICO)
    res_met = await classifier.classify("¿Cómo aplico MECE?")
    assert res_met.query_type == "METODOLOGICO"


def test_corrective_evaluator_threshold():
    """Test 2: CorrectivenessEvaluator — threshold"""
    evaluator = CorrectivenessEvaluator()
    evaluator.RELEVANCE_THRESHOLD = 0.65

    # Chunk con score=0.72 (PASA)
    chunk_pass = RetrievedChunk(
        chunk_id="1", document_id="doc1", text="test", 
        score=0.72, metadata={}
    )
    # Chunk con score=0.36 (FALLA)
    chunk_fail = RetrievedChunk(
        chunk_id="2", document_id="doc2", text="test", 
        score=0.36, metadata={}
    )

    result = evaluator.evaluate([chunk_pass, chunk_fail], "query")
    assert result.status == "OK"
    assert len(result.approved_chunks) == 1
    assert result.approved_chunks[0].chunk_id == "1"


@pytest.mark.asyncio
async def test_hybrid_retrieval_query_call():
    """Test 3: Búsqueda híbrida llama a Qdrant correctamente"""
    mock_client = MagicMock()
    mock_client.query = MagicMock(return_value=[])
    hybrid = HybridRetriever(qdrant_client=mock_client, collection_name="test", embedder=AsyncMock())
    
    await hybrid.retrieve("query text", agent_name="financial", client_id="test_client", top_k=5)
    
    assert mock_client.query.called
    kwargs = mock_client.query.call_args.kwargs
    assert kwargs["query_text"] == "query text"
    assert kwargs["limit"] == 5


def test_insufficient_context():
    """Test 4: OrchestratedResult — INSUFFICIENT_CONTEXT"""
    evaluator = CorrectivenessEvaluator()
    evaluator.RELEVANCE_THRESHOLD = 0.99 # Forzamos fallo
    
    chunk_fail = RetrievedChunk(
        chunk_id="1", document_id="doc1", text="test", 
        score=0.4, metadata={}
    )
    result = evaluator.evaluate([chunk_fail], "query")
    
    assert result.status == "INSUFFICIENT_CONTEXT"
    assert len(result.approved_chunks) == 0


@pytest.mark.asyncio
async def test_retrocompatibility_original_search():
    """Test 5: Compatibilidad retroactiva"""
    mock_embedder = AsyncMock()
    mock_embedder.embed_single = AsyncMock(return_value=[0.1] * 768)

    mock_client = MagicMock()
    mock_hit = MagicMock()
    mock_hit.score = 0.9
    mock_hit.payload = {
        "chunk_id": "old_chunk",
        "document_title": "old_doc",
        "content": "old_content",
        "agent_access": ["all"]
    }
    
    mock_response = MagicMock()
    mock_response.points = [mock_hit]
    mock_client.query_points.return_value = mock_response

    engine = QueryEngine(embedder=mock_embedder, collection="test_col")
    engine.client = mock_client
    
    results = await engine.search(query="test", agent_name="financial", final_k=1, client_id="test_client")
    
    assert len(results) == 1
    assert isinstance(results[0], SearchResult)
    assert results[0].chunk_id == "old_chunk"
