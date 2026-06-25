"""
Arista condicional: distribución del Enjambre tras el EIP Router.

El router decide qué agentes activar (active_agents) y despachamos
solo a esos agentes.
"""
from __future__ import annotations

from ..state import GraphState


def distribute_swarm(state: GraphState) -> str:
    """
    Selecciona el primer agente activo para ejecutar secuencialmente.
    """
    if "process" in state.active_agents:
        return "process_node"
    elif "data_engineer" in state.active_agents:
        return "data_engineer_node"
    return "financial_node"
