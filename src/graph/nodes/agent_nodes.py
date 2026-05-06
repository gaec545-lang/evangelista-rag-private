"""
Nodos del Enjambre Multi-Agente EIP.

Cada agente recibe inputs del SCQA, consulta las herramientas periféricas
(RAG y Sandbox) y emite su veredicto parcial que converge en el Consenso.
"""
from __future__ import annotations

from ..state import GraphState, NodeStatus
import structlog

logger = structlog.get_logger(__name__)


def financial_node(state: GraphState) -> dict:
    """
    Financial Agent — aísla métricas por unidad, ROI, LTV/CAC, proyecciones.

    Consulta el Motor RAG para metodología y el Sandbox para cálculos.
    TODO: Implementar invocación del Financial LLM + tool calling.
    """
    log = state.log_node("financial_node", NodeStatus.COMPLETED, "hypothesis_generated")
    logger.info("financial_node", scqa=state.scqa_input.get("situacion", ""))

    return {
        "current_agent": "financial",
        "financial_hypothesis": {
            "metric": "pending_implementation",
            "value": 0.0,
            "confidence": 0.0,
            "assumptions": ["placeholder"],
        },
        "node_history": [*state.node_history, "financial_node"],
        "mermaid_log": [*state.mermaid_log, log],
    }


def process_node(state: GraphState) -> dict:
    """
    Process Agent — mapea cuellos de botella operativos, logística, inventario.

    Envía retroalimentación ('Fricción Operativa') al Financial Agent.
    TODO: Implementar invocación del Process LLM.
    """
    log = state.log_node("process_node", NodeStatus.COMPLETED, "friction_identified")
    logger.info("process_node")

    return {
        "current_agent": "process",
        "process_friction": {
            "operational_constraint": "pending_implementation",
            "impact": 0.0,
            "bottleneck": "placeholder",
        },
        "node_history": [*state.node_history, "process_node"],
        "mermaid_log": [*state.mermaid_log, log],
    }


def data_engineer_node(state: GraphState) -> dict:
    """
    Data Engineer Agent — abstracción Zero-Trust, acceso a ERPs, Text-to-SQL.

    Envía retroalimentación ('Viabilidad de Datos') al Financial Agent.
    TODO: Implementar conexión a ERPs + Text-to-SQL.
    """
    log = state.log_node("data_engineer_node", NodeStatus.COMPLETED, "data_viability_checked")
    logger.info("data_engineer_node")

    return {
        "current_agent": "data_engineer",
        "data_viability": {
            "data_integrity": "pending_implementation",
            "missing_fields": [],
            "etl_feasible": True,
        },
        "node_history": [*state.node_history, "data_engineer_node"],
        "mermaid_log": [*state.mermaid_log, log],
    }
