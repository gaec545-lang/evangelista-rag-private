"""
Nodo Hallucination Check (Self-Reflective RAG):
Verifica que la respuesta está fundamentada en las fuentes recuperadas.
Si no lo está Y quedan reintentos disponibles, incrementa retry_count
para que la edge function decida re-generar.
"""
from __future__ import annotations

from ..state import GraphState, NodeStatus
from src.llm.factory import get_llm_client
import json
import structlog

logger = structlog.get_logger()

HALLUCINATION_PROMPT = """Evalúa si la siguiente respuesta está FUNDAMENTADA en los documentos proporcionados.

Documentos fuente:
{sources}

Respuesta generada:
{generation}

¿La respuesta contiene afirmaciones que NO están respaldadas por los documentos?
¿Inventa datos, cifras o estadísticas que no aparecen en las fuentes?

Responde SOLO con JSON:
{{"grounded": true|false, "reasoning": "explicación de qué está o no fundamentado"}}"""


async def check_hallucination(state: GraphState) -> GraphState:
    """Self-RAG: Verifica que la respuesta no alucine."""
    llm = get_llm_client()

    docs = state.relevant_documents or state.documents
    sources_text = "\n\n".join([f"[{d.title}]: {d.content[:800]}" for d in docs[:5]])

    if not sources_text:
        return state.model_copy(update={
            "hallucination_check": True,
            "hallucination_reasoning": "Sin fuentes para verificar — asumiendo válida.",
            "current_node": "hallucination_check",
            "node_history": state.node_history + ["hallucination_check"],
            "mermaid_log": state.mermaid_log + [
                state.log_node("hallucination_check", NodeStatus.COMPLETED, "no sources → pass")
            ],
        })

    response = await llm.generate(
        prompt=HALLUCINATION_PROMPT.format(
            sources=sources_text,
            generation=state.generation[:2000],
        ),
        temperature=0.0,
        max_tokens=200,
    )

    try:
        clean = response.strip()
        if "```" in clean:
            clean = clean.split("```")[1].replace("json", "").strip()
        parsed = json.loads(clean)
        grounded = parsed.get("grounded", True)
        reasoning = parsed.get("reasoning", "")
    except (json.JSONDecodeError, KeyError):
        grounded = True
        reasoning = "No se pudo evaluar — asumiendo válida."

    logger.info("hallucination_check", grounded=grounded, reasoning=reasoning[:100])

    # Incrementar retry_count si se detectó alucinación y quedan reintentos
    new_retry = state.retry_count + (1 if not grounded else 0)

    return state.model_copy(update={
        "hallucination_check": grounded,
        "hallucination_reasoning": reasoning,
        "retry_count": new_retry,
        "current_node": "hallucination_check",
        "node_history": state.node_history + ["hallucination_check"],
        "mermaid_log": state.mermaid_log + [
            state.log_node(
                "hallucination_check", NodeStatus.COMPLETED,
                "grounded" if grounded else f"HALLUCINATED (retry {new_retry})"
            )
        ],
    })
