"""
Nodos del Enjambre Multi-Agente EIP.

Cada agente recibe inputs del SCQA y su tarea específica despachada por el Orquestador.
Consultará su contexto y skills definidos en el Vault (.md) y utilizará LLaMA 70B
para síntesis profunda (partición de modelos).
"""
from __future__ import annotations

import os
from pathlib import Path
from ..state import GraphState, NodeStatus
from src.llm.factory import get_llm_client
import structlog

logger = structlog.get_logger(__name__)

VAULT_AGENTS_DIR = Path(r"E:\Evangelista company\Evangelista Intelligence Platform\Evangelista-Obsidian\evangelista-vault\agents")

def _load_agent_context(agent_name: str) -> str:
    """Carga el contexto, skills y prompts del agente desde el Vault."""
    md_path = VAULT_AGENTS_DIR / f"{agent_name}.md"
    if md_path.exists():
        try:
            with open(md_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            logger.error("failed_to_load_agent_md", agent=agent_name, error=str(e))
    return f"Contexto por defecto para {agent_name}."

async def _run_agent(state: GraphState, agent_name: str) -> str:
    """Ejecución genérica de un especialista usando el LLM."""
    my_tasks = [t for t in state.tasks if t.get("agent") == agent_name]
    task_desc = my_tasks[0].get("task", "Análisis general") if my_tasks else "Análisis general"
    
    agent_context = _load_agent_context(agent_name)
    
    # ponytail: include previous grader feedback if any to help agent adapt
    feedback_text = str(state.grader_feedback) if state.grader_feedback else "Ninguno"
    
    prompt = f"""Eres el agente especialista: {agent_name}.
Tu contexto y habilidades provienen de tu definición en el Vault:
---
{agent_context}
---
Tu tarea asignada por el Orquestador es:
{task_desc}

Consulta general del usuario: {state.question if getattr(state, "question", None) else str(state.scqa_input)}
Información disponible en RAG/Web: {state.documents}
Feedback del Grader/Orquestador: {feedback_text}

Analiza y proporciona tu dictamen experto.
"""
    llm = get_llm_client("groq-llama-70b") # Modelo grande para síntesis
    response = await llm.generate(
        prompt=prompt,
        system_prompt="Responde de manera profesional y estructurada como consultor de Evangelista & Co.",
        temperature=0.2,
        max_tokens=800
    )
    return response

async def financial_node(state: GraphState) -> dict:
    """Financial Agent — aísla métricas por unidad, ROI, LTV/CAC, proyecciones."""
    # ponytail: wait for process and data_engineer if active before executing final valuation
    active_others = [a for a in state.active_agents if a != "financial"]
    is_process_done = "process" not in active_others or ("process_node" in state.node_history) or bool(state.process_friction)
    is_data_eng_done = "data_engineer" not in active_others or ("data_engineer_node" in state.node_history) or bool(state.data_viability)
    
    if not (is_process_done and is_data_eng_done):
        return {}

    resultado = await _run_agent(state, "financial")
    
    log = state.log_node("financial_node", NodeStatus.COMPLETED, "financial_analysis_complete")
    logger.info("financial_node_complete")

    # ponytail: state update dictionary avoids Pydantic model copy overhead and node_history duplication
    return {
        "financial_hypothesis": {
            "metric": "ROI/Valuation",
            "value": 0.0,
            "confidence": 0.9,
            "assumptions": [resultado],
        },
        "current_agent": "financial",
        "node_history": ["financial_node"],
        "mermaid_log": [log],
    }


async def process_node(state: GraphState) -> dict:
    """Process Agent — mapea cuellos de botella operativos, logística, inventario."""
    resultado = await _run_agent(state, "process")
    
    log = state.log_node("process_node", NodeStatus.COMPLETED, "process_analysis_complete")
    logger.info("process_node_complete")

    # ponytail: state update dictionary avoids Pydantic model copy overhead and node_history duplication
    return {
        "process_friction": {
            "operational_constraint": "Identified by LLM",
            "impact": 0.8,
            "bottleneck": resultado,
        },
        "current_agent": "process",
        "node_history": ["process_node"],
        "mermaid_log": [log],
    }


async def data_engineer_node(state: GraphState) -> dict:
    """Data Engineer Agent — abstracción Zero-Trust, acceso a ERPs, Text-to-SQL."""
    resultado = await _run_agent(state, "data_engineer")
    
    log = state.log_node("data_engineer_node", NodeStatus.COMPLETED, "data_viability_complete")
    logger.info("data_engineer_node_complete")

    # ponytail: state update dictionary avoids Pydantic model copy overhead and node_history duplication
    return {
        "data_viability": {
            "data_integrity": resultado,
            "missing_fields": [],
            "etl_feasible": True,
        },
        "current_agent": "data_engineer",
        "node_history": ["data_engineer_node"],
        "mermaid_log": [log],
    }
