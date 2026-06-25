"""
Arista condicional: decisión del Grader EIP.

CORREGIDO: Si hallucination_flag=True → rechaza y devuelve al ENJAMBRE
(financial_node), NO al consensus. Esto permite a los agentes regenerar
la respuesta procesando la crítica del grader.

Si hallucination_flag=False → avanza al Synthesizer.
"""
from __future__ import annotations

from ..state import GraphState


def decide_after_eip_grader(state: GraphState) -> str:
    """
    Grader → financial_node (rechazo) | eip_synthesizer (aprobado).
    """
    if state.hallucination_flag and state.retry_count < state.max_retries:
        if state.active_agents:
            return f"{state.active_agents[0]}_node"
        return "financial_node"  # rechaza: enjambre regenera
    return "eip_synthesizer"  # aprobado u límite de reintentos alcanzado: va al syn
