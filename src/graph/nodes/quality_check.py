"""
Nodo Quality Check (Self-Reflective RAG):
Verifica que la respuesta realmente contesta la pregunta original.
Si no es útil Y quedan reintentos, incrementa retry_count para que
la edge function decida volver al retriever.
"""
from __future__ import annotations

from ..state import GraphState, NodeStatus
from src.llm.factory import get_llm_client
import json
import structlog

logger = structlog.get_logger()

QUALITY_PROMPT = """Evalúa si la siguiente respuesta es ÚTIL y RESPONDE DIRECTAMENTE a la pregunta del usuario.

Pregunta original: {question}

Respuesta generada: {generation}

Criterios:
1. ¿Responde directamente lo que se preguntó? (no da rodeos)
2. ¿Incluye datos concretos cuando se piden cifras?
3. ¿Es accionable? (el usuario puede tomar una decisión con esta información)

Responde SOLO con JSON:
{{"useful": true|false, "reasoning": "explicación"}}"""


async def check_quality(state: GraphState) -> GraphState:
    """Self-RAG: Verifica que la respuesta sea útil y responda la pregunta."""
    llm = get_llm_client()

    response = await llm.generate(
        prompt=QUALITY_PROMPT.format(
            question=state.question,
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
        useful = parsed.get("useful", True)
        reasoning = parsed.get("reasoning", "")
    except (json.JSONDecodeError, KeyError):
        useful = True
        reasoning = "No se pudo evaluar — asumiendo útil."

    logger.info("quality_check", useful=useful, reasoning=reasoning[:100])

    # Incrementar retry_count si la respuesta no es útil y quedan reintentos
    new_retry = state.retry_count + (1 if not useful else 0)

    return state.model_copy(update={
        "quality_check": useful,
        "quality_reasoning": reasoning,
        "retry_count": new_retry,
        "current_node": "quality_check",
        "node_history": state.node_history + ["quality_check"],
        "mermaid_log": state.mermaid_log + [
            state.log_node(
                "quality_check", NodeStatus.COMPLETED,
                "useful" if useful else f"NOT USEFUL (retry {new_retry})"
            )
        ],
    })
