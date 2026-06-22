"""
Nodo Synth del Enjambre Multi-Agente EIP (Synthesizer).

Empaqueta el swarm_consensus en final_pdf_data para inyección
en PyMuPDF (template corporativa oficial).
"""
from __future__ import annotations

from ..state import GraphState, NodeStatus
import structlog

logger = structlog.get_logger(__name__)


async def eip_synthesizer(state: GraphState) -> dict:
    """
    Synthesizer — convierte el swarm_consensus en final_response (Markdown) y final_pdf_data.
    """
    from src.llm.factory import get_llm_client
    llm = get_llm_client()

    system_prompt = "Eres un consultor senior redactando un informe final ejecutivo y pulido."
    prompt = f"""
    Redacta una respuesta final pulida en formato Markdown basándote en el siguiente consenso
    del enjambre de agentes:
    
    {state.swarm_consensus}
    
    Asegúrate de que la respuesta sea profesional, estructurada, clara y lista para presentar.
    """
    
    try:
        final_markdown = await llm.generate(prompt=prompt, system_prompt=system_prompt)
    except Exception as e:
        logger.error("eip_synthesizer_generation_error", error=str(e))
        final_markdown = f"Error al generar síntesis: {str(e)}\n\nConsenso original:\n{state.swarm_consensus}"

    log = state.log_node("eip_synthesizer", NodeStatus.COMPLETED, "synthesis_complete")
    logger.info("eip_synthesizer")

    pdf_data = {
        "executive_summary": "Generado desde síntesis",
        "kpi_impact": {},
        "recommendations": [],
        "cost_of_inaction": 0.0,
        "sources": [],
    }

    return {
        "final_pdf_data": pdf_data,
        "final_response": final_markdown,
        "node_history": [*state.node_history, "eip_synthesizer"],
        "mermaid_log": [*state.mermaid_log, log],
    }
