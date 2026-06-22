"""
Nodo Grader del Enjambre Multi-Agente EIP (Self-RAG).

Evalúa el swarm_consensus y determina si hay alucinación o falta de datos.
Si rechaza, devuelve al enjambre. Si aprueba, envía al Synthesizer.
"""
from __future__ import annotations

from ..state import GraphState, NodeStatus
import structlog

logger = structlog.get_logger(__name__)


import json

async def eip_grader(state: GraphState) -> dict:
    """
    Self-RAG Evaluator — revisa el swarm_consensus para detectar:
    - Alucinación (datos sin fuente)
    - Falta de contexto (campos vacíos)
    - Conflictos entre agentes (fricción > threshold)
    """
    from src.llm.factory import get_llm_client
    llm = get_llm_client("groq-llama-70b")

    system_prompt = "Eres un Evaluador (Grader) crítico para un sistema multi-agente. Responde ÚNICAMENTE en JSON."
    prompt = f"""
    Evalúa el siguiente consenso generado por el enjambre de agentes:
    
    {state.swarm_consensus}
    
    Determina si existe alguna alucinación evidente, si faltan datos importantes,
    o si hay campos marcados como 'pending_implementation' o vacíos que deberían
    estar completos.
    
    Formato de salida JSON estricto:
    {{
        "hallucination": true/false,
        "reason": "Explicación breve"
    }}
    """
    
    try:
        response_text = await llm.generate(prompt=prompt, system_prompt=system_prompt, temperature=0.1)
        content = response_text.replace('```json', '').replace('```', '').strip()
        result = json.loads(content)
        hallucination_flag = result.get("hallucination", False)
        reason = result.get("reason", "")
    except Exception as e:
        logger.error("eip_grader_json_parse_error", error=str(e))
        hallucination_flag = False
        reason = "Error al evaluar consenso"

    status = "rejected" if hallucination_flag else "approved"
    log = state.log_node("eip_grader", NodeStatus.COMPLETED, status)
    logger.info("eip_grader", flag=hallucination_flag, reason=reason)

    grader_feedback = []
    if hallucination_flag:
        grader_feedback = [{"agent": "grader", "feedback": reason}]

    return {
        "hallucination_flag": hallucination_flag,
        "rejection_reason": reason,
        "grader_feedback": grader_feedback,
        "node_history": [*state.node_history, "eip_grader"],
        "mermaid_log": [*state.mermaid_log, log],
    }
