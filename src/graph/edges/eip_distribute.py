"""
Arista condicional: distribución del Enjambre tras el EIP Router.

El router no bifurca entre RAG y Sandbox. Simplemente distribuye el
trabajo a los 3 agentes en paralelo (debate multi-agente).
"""
from __future__ import annotations

from ..state import GraphState


def distribute_swarm(state: GraphState) -> list[str]:
    """
    Siempre activa los 3 agentes en paralelo.
    El debate cruzado ocurre en las aristas siguientes.
    """
    return ["financial_node", "process_node", "data_engineer_node"]
