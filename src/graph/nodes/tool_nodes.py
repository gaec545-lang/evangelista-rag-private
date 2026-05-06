"""
Nodos de Herramientas del Enjambre Multi-Agente EIP.

RAG_NODE: Motor RAG (búsqueda semántica) — Embeddings → VectorDB → Contexto.
Sandbox_NODE: Ejecución matemática aislada (Monte Carlo, Text-to-SQL).

Según el PED, estos son TOOLS que los agentes consultan — no son rutas
independientes desde el Router.
"""
from __future__ import annotations

from ..state import GraphState, NodeStatus
import structlog

logger = structlog.get_logger(__name__)


def rag_node(state: GraphState) -> dict:
    """
    Motor RAG — Búsqueda Semántica.

    Flujo interno: Embeddings → Qdrant (VectorDB) → Contexto Vault.
    Invocado por los agentes cuando necesitan metodología o teoría.
    TODO: Implementar vector search contra Qdrant.
    """
    log = state.log_node("rag_node", NodeStatus.COMPLETED, "context_retrieved")
    logger.info("rag_node", agent=state.current_agent)

    return {
        "node_history": [*state.node_history, "rag_node"],
        "mermaid_log": [*state.mermaid_log, log],
    }


def sandbox_node(state: GraphState) -> dict:
    """
    Sandbox Matemático — Code Execution Sandbox.

    Recibe parámetros del agente y ejecuta Python/Pandas (Monte Carlo,
    cálculos financieros, etc.). El LLM solo lee la salida — jamás calcula.
    TODO: Implementar Code Execution Sandbox aislado.
    """
    log = state.log_node("sandbox_node", NodeStatus.COMPLETED, "computation_executed")
    logger.info("sandbox_node", agent=state.current_agent)

    return {
        "node_history": [*state.node_history, "sandbox_node"],
        "mermaid_log": [*state.mermaid_log, log],
    }
