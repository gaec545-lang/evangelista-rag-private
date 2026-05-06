"""Tests para el motor de Advanced RAG (LangGraph)."""
import pytest
from unittest.mock import AsyncMock, patch
from src.graph.state import GraphState
from src.graph.builder import run_graph

@pytest.mark.asyncio
async def test_run_graph_basic_flow():
    """Valida que el grafo se ejecute y devuelva un estado válido."""
    question = "Cual es el setup fee para 2 sucursales?"
    
    # Mock de los nodos para evitar llamadas reales a LLM/VectorDB en tests unitarios
    with patch("src.graph.nodes.router.route_question", new_callable=AsyncMock) as mock_router:
        mock_router.return_value = {"route": "rag"}
        
        with patch("src.graph.builder.build_graph") as mock_build:
            # Creamos un grafo mock que simplemente retorna un estado final
            mock_compiled = AsyncMock()
            mock_compiled.ainvoke.return_value = {
                "question": question,
                "final_response": "El setup fee es de $10,000 MXN.",
                "confidence": 0.95,
                "node_history": ["router", "retriever", "generator", "synthesizer"],
                "generation_sources": ["Documento de Precios v1.2"]
            }
            mock_build.return_value = mock_compiled
            
            state = await run_graph(question=question)
            
            assert isinstance(state, GraphState)
            assert state.question == question
            assert "El setup fee" in state.final_response
            assert state.confidence > 0.8
            assert "router" in state.node_history
            assert len(state.generation_sources) > 0
