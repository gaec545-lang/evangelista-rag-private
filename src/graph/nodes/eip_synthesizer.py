"""
Nodo Synth del Enjambre Multi-Agente EIP (Synthesizer).

Empaqueta el swarm_consensus en final_pdf_data para inyección
en PyMuPDF (template corporativa oficial).
"""
from __future__ import annotations

from ..state import GraphState, NodeStatus
import structlog

logger = structlog.get_logger(__name__)


def eip_synthesizer(state: GraphState) -> dict:
    """
    Synthesizer — convierte el swarm_consensus en final_pdf_data.

    TODO: Integrar con proposals/generator.py para estampado en PDF.
    """
    log = state.log_node("eip_synthesizer", NodeStatus.COMPLETED, "synthesis_complete")
    logger.info("eip_synthesizer")

    pdf_data = {
        "executive_summary": "pending_implementation",
        "kpi_impact": {},
        "recommendations": state.swarm_consensus.get("recommendations", []),
        "cost_of_inaction": 0.0,
        "sources": [],
    }

    return {
        "final_pdf_data": pdf_data,
        "final_response": "Synthesis complete (stub)",
        "node_history": [*state.node_history, "eip_synthesizer"],
        "mermaid_log": [*state.mermaid_log, log],
    }
