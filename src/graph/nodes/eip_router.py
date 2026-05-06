"""
Nodo Router del Enjambre Multi-Agente EIP.

Recibe el SCQA del Consultor y asigna el trabajo al Enjambre de Agentes.
No bifurca entre RAG y Sandbox — los agentes son los que consultan
las herramientas durante su razonamiento (PED — Protocolo de Ejecución Determinista).
"""
from __future__ import annotations

from ..state import GraphState, NodeStatus
import structlog

logger = structlog.get_logger(__name__)


def eip_router(state: GraphState) -> dict:
    """
    Asigna el trabajo al Enjambre de Agentes.

    TODO: Implementar lógica de assignment basada en el tipo de scqa_input.
    Por ahora, inicia en el Financial Agent.
    """
    log = state.log_node("eip_router", NodeStatus.COMPLETED, "assigned_to_swarm")
    logger.info("eip_router", scqa=state.scqa_input)

    return {
        "current_agent": "financial",
        "node_history": [*state.node_history, "eip_router"],
        "mermaid_log": [*state.mermaid_log, log],
    }
