"""
Nodo Consenso del Enjambre Multi-Agente EIP.

Converge los resultados de los especialistas en un dictamen unificado.
"""
from __future__ import annotations

from ..state import GraphState, NodeStatus
from src.llm.factory import get_llm_client
import structlog

logger = structlog.get_logger(__name__)

CONSENSUS_PROMPT = """Eres el Nodo de Consenso del Concilio Maestro de Evangelista & Co.
Tu tarea es unificar y ponderar los hallazgos de los agentes especialistas activos.

Resultados de los agentes:
Finanzas: {finanzas}
Procesos: {procesos}
Datos: {datos}

Genera un consenso ponderado y profesional. Si hay fricción en procesos o viabilidad de datos baja, pondera los riesgos.
Escribe un resumen ejecutivo consolidado con las recomendaciones, los riesgos identificados y la estrategia sugerida, en formato Markdown.
"""

async def consensus_node(state: GraphState) -> dict:
    """
    Convergencia: unifica las hipótesis de los agentes usando un LLM para síntesis.
    """
    llm = get_llm_client("groq-llama-70b")
    
    finanzas = str(state.financial_hypothesis) if state.financial_hypothesis else "Sin datos"
    procesos = str(state.process_friction) if state.process_friction else "Sin datos"
    datos = str(state.data_viability) if state.data_viability else "Sin datos"
    
    prompt = CONSENSUS_PROMPT.format(finanzas=finanzas, procesos=procesos, datos=datos)
    
    response = await llm.generate(
        prompt=prompt,
        system_prompt="Escribe un resumen ejecutivo consolidado del debate de los especialistas.",
        temperature=0.2,
        max_tokens=600
    )
    
    log = state.log_node("consensus", NodeStatus.COMPLETED, "convergence_achieved")
    logger.info("consensus_node", response_len=len(response))

    # ponytail: state update dictionary avoids Pydantic model copy overhead and node_history duplication
    return {
        "swarm_consensus": response,
        "node_history": ["consensus"],
        "mermaid_log": [log],
    }
