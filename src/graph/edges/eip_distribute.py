"""
Arista condicional: distribución del Enjambre tras el EIP Router.

El router decide qué agentes activar (active_agents) y despachamos
solo a esos agentes.
"""
from __future__ import annotations

from ..state import GraphState


def distribute_swarm(state: GraphState) -> list[str]:
    """
    Despacha el estado solo a los agentes activos.
    """
    if not state.active_agents:
        # Fallback de seguridad
        return ["financial_node"]
    
    return [f"{agent}_node" for agent in state.active_agents]
