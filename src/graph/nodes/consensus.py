"""
Nodo Consenso del Enjambre Multi-Agente EIP.

Converge los resultados de Financial, Process y Data Engineer en un
dictamen unificado que avanza al Grader.
"""
from __future__ import annotations

from ..state import GraphState, NodeStatus
import structlog

logger = structlog.get_logger(__name__)


def consensus_node(state: GraphState) -> dict:
    """
    Convergencia: unifica financial_hypothesis + process_friction + data_viability
    en un solo swarm_consensus coherente.

    TODO: Implementar lógica de consenso ponderado (ej. si data_viability
    es baja, reducir confidence del consenso proporcionalmente).
    """
    log = state.log_node("consensus", NodeStatus.COMPLETED, "convergence")
    logger.info("consensus_node")

    consensus = {
        "financial": state.financial_hypothesis,
        "process": state.process_friction,
        "data": state.data_viability,
        "unified_confidence": 0.0,
        "recommendations": [],
    }

    return {
        "swarm_consensus": consensus,
        "node_history": [*state.node_history, "consensus"],
        "mermaid_log": [*state.mermaid_log, log],
    }
