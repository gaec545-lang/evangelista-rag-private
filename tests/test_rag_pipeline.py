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

    # Chunk con semantic=0.8, bm25=0.6 → weighted = 0.6*0.8 + 0.4*0.6 = 0.48 + 0.24 = 0.72 (PASA)
    chunk_pass = RetrievedChunk(
        chunk_id="1", document_id="doc1", text="test", 
        score=0.0, semantic_score=0.8, bm25_score=0.6, metadata={}
    )
    # Chunk con semantic=0.4, bm25=0.3 → weighted = 0.6*0.4 + 0.4*0.3 = 0.24 + 0.12 = 0.36 (FALLA)
    chunk_fail = RetrievedChunk(
        chunk_id="2", document_id="doc2", text="test", 
        score=0.0, semantic_score=0.4, bm25_score=0.3, metadata={}
    )

    result = evaluator.evaluate([chunk_pass, chunk_fail], "query")
    assert result.status == "OK"
    assert len(result.approved_chunks) == 1
    assert result.approved_chunks[0].chunk_id == "1"


def test_reciprocal_rank_fusion():
    """Test 3: RRF — orden correcto"""
    hybrid = HybridRetriever(qdrant_client=MagicMock(), collection_name="test", embedder=AsyncMock())
    
    bm25 = [
        ("chunk1", 0.9, "text1"), # rank 0
        ("chunk2", 0.8, "text2"), # rank 1
    ]
    qdrant = [
        ("chunk3", 0.85, {"text": "text3"}), # rank 0
        ("chunk2", 0.80, {"text": "text2"}), # rank 1
        ("chunk1", 0.70, {"text": "text1"}), # rank 2
    ]
    
    # RRF (k=60):
    # chunk1: 1/61 (bm25) + 1/63 (qdrant) = 0.01639 + 0.01587 = 0.03226
    # chunk2: 1/62 (bm25) + 1/62 (qdrant) = 0.01612 + 0.01612 = 0.03224
    # chunk3: 0 (bm25) + 1/61 (qdrant) = 0.01639
    
    fused = hybrid._reciprocal_rank_fusion(bm25, qdrant, k=60)
    
    assert len(fused) == 3
    assert fused[0].chunk_id == "chunk1"
    assert fused[1].chunk_id == "chunk2"
    assert fused[2].chunk_id == "chunk3"


def test_insufficient_context():
    """Test 4: OrchestratedResult — INSUFFICIENT_CONTEXT"""
    evaluator = CorrectivenessEvaluator()
    evaluator.RELEVANCE_THRESHOLD = 0.99 # Forzamos fallo
    
    chunk_fail = RetrievedChunk(
        chunk_id="1", document_id="doc1", text="test", 
        score=0.0, semantic_score=0.4, bm25_score=0.3, metadata={}
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
    
    results = await engine.search(query="test", agent_name="financial", final_k=1)
    
    assert len(results) == 1
    assert isinstance(results[0], SearchResult)
    assert results[0].chunk_id == "old_chunk"
