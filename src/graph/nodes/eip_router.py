"""
Nodo Router del Enjambre Multi-Agente EIP (Orquestador).

Recibe el SCQA del Consultor y asigna el trabajo al Enjambre de Agentes.
Usa partición de modelos: Groq 8B para ruteo rápido y validación de complejidad.
"""
from __future__ import annotations

import json
from ..state import GraphState, NodeStatus
from src.llm.factory import get_llm_client
import structlog

logger = structlog.get_logger(__name__)

ROUTER_PROMPT = """Eres el Orquestador del Concilio Maestro de Evangelista & Co.
Dada la siguiente consulta del usuario, debes descomponerla en tareas para los subagentes especialistas y decidir cuáles activar.

Agentes disponibles:
- "financial": Especialista en finanzas corporativas, valuaciones, modelos de precios.
- "process": Especialista en procesos, reingeniería, mapas de valor, operaciones.
- "data_engineer": Especialista en arquitectura de datos, ETL, viabilidad de datos.

Responde SOLO con un JSON estricto con esta estructura:
{{
  "active_agents": ["financial", "process"],
  "tasks": [
    {{"agent": "financial", "task": "Calcular la Tasa de Descuento"}},
    {{"agent": "process", "task": "Mapear procesos As-Is"}}
  ]
}}

Consulta: {question}
SCQA Contexto: {scqa}
Feedback anterior: {feedback}
"""

async def eip_router(state: GraphState) -> dict:
    """
    Asigna el trabajo al Enjambre de Agentes basándose en la complejidad y la pregunta.
    """
    llm = get_llm_client("groq-llama-8b")
    
    feedback_text = str(state.grader_feedback) if state.grader_feedback else "Ninguno"
    
    response = await llm.generate(
        prompt=ROUTER_PROMPT.format(
            question=state.question if getattr(state, "question", None) else str(state.scqa_input),
            scqa=state.scqa_input,
            feedback=feedback_text
        ),
        system_prompt="",
        temperature=0.0,
        max_tokens=300
    )
    
    try:
        clean = response.strip()
        if clean.startswith("```"):
            clean = clean.split("```")[1].replace("json", "").strip()
        parsed = json.loads(clean)
        active_agents = parsed.get("active_agents", ["financial"])
        tasks = parsed.get("tasks", [{"agent": "financial", "task": "Responder consulta general"}])
    except (json.JSONDecodeError, KeyError) as e:
        logger.error("eip_router_parse_error", error=str(e), response=response)
        active_agents = ["financial"]
        tasks = [{"agent": "financial", "task": "Responder consulta general (Fallback)"}]
    
    log = state.log_node("eip_router", NodeStatus.COMPLETED, f"assigned_to: {active_agents}")
    logger.info("eip_router_success", active_agents=active_agents, tasks=tasks)

    # ponytail: don't hijack state.route, agents request tools themselves.
    return {
        "active_agents": active_agents,
        "tasks": tasks,
        "route": None,
        "node_history": ["eip_router"],
        "mermaid_log": [log],
    }
