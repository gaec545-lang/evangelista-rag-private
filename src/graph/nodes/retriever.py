"""
Nodo Retriever: Busca documentos en Qdrant con filtros de seguridad.
Usa la query original o una query refinada si CRAG pidió refinar.
"""
from __future__ import annotations

from ..state import GraphState, RetrievedDocument, NodeStatus
from src.retrieval.query_engine import QueryEngine
from src.agents.registry import AgentRegistry
import structlog

logger = structlog.get_logger()

# Agentes que mejor cubren cada dominio de ruta
_ROUTE_TO_AGENT = {
    "rag":   "financial",
    "tools": "financial",
    "web":   "financial",
    "multi": "financial",
}


async def retrieve_documents(state: GraphState) -> GraphState:
    """Busca documentos relevantes en el knowledge base (Qdrant)."""
    query = state.refined_query or state.question

    # Elegir agente para el filtro de seguridad
    route = state.route or "rag"
    preferred = _ROUTE_TO_AGENT.get(route, "financial")

    # Validar que el agente exista; si no, usar el primero disponible
    available = AgentRegistry.list_agents()
    agent_name = preferred if preferred in available else (available[0] if available else "financial")

    engine = QueryEngine()

    try:
        results = await engine.search(
            query=query,
            agent_name=agent_name,
            top_k=10,
            final_k=6,
        )
    except Exception as exc:
        logger.error("retriever_error", error=str(exc))
        results = []

    documents = [
        RetrievedDocument(
            id=r.document_id,
            title=r.document_title,
            content=r.content,
            source="qdrant",
            score=r.score,
        )
        for r in results
    ]

    logger.info(
        "retriever_results",
        count=len(documents),
        agent=agent_name,
        top_score=documents[0].score if documents else 0,
    )

    return state.model_copy(update={
        "documents": documents,
        "current_node": "retriever",
        "node_history": state.node_history + ["retriever"],
        "mermaid_log": state.mermaid_log + [state.log_node("retriever", NodeStatus.COMPLETED, f"{len(documents)} docs")],
    })
