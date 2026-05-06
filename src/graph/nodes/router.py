from ..state import GraphState
from src.llm.factory import get_llm_client
import json
import structlog

logger = structlog.get_logger()

ROUTER_PROMPT = """Eres un clasificador de preguntas para Evangelista & Co., una firma de consultoría de Intelligence Architecture.

Clasifica la siguiente pregunta en UNA de estas categorías:

- "rag": La respuesta está en el knowledge base interno (protocolos, casos, fórmulas, playbooks, patrones de hallazgos, benchmarks sectoriales). Usar para: preguntas sobre metodología Evangelista, casos de estudio, fórmulas de pricing, hallazgos típicos por sector, ERPs mexicanos.
- "tools": Requiere ejecutar un cálculo matemático preciso (Factor Γ, α, β, Setup Fee, ROI, Success Fee). Usar para: "calcula", "cuánto cuesta", "qué precio".
- "web": La información NO está en el knowledge base y requiere datos actuales de internet (regulaciones recientes, noticias del sector, datos macro de INEGI, competidores).
- "multi": Necesita COMBINAR knowledge base + cálculos + posiblemente web. Usar para: preguntas complejas que cruzan dominios. Ejemplo: "Analiza a una textilera con 3 plantas y calcula el ROI proyectado basándote en casos similares."

Responde SOLO con un JSON:
{{"route": "rag|tools|web|multi", "reasoning": "explicación corta de por qué"}}

Ejemplo de Salida:
{{"route": "rag", "reasoning": "La pregunta requiere datos históricos de la empresa."}}

Pregunta: {question}"""

async def route_question(state: GraphState) -> GraphState:
    """Clasifica la pregunta y decide la ruta."""
    # Usar modelo rápido para routing (por defecto groq-llama-70b)
    llm = get_llm_client()
    
    response = await llm.generate(
        prompt=ROUTER_PROMPT.format(question=state.question),
        system_prompt="",
        temperature=0.0,
        max_tokens=150
    )
    
    try:
        clean = response.strip()
        if clean.startswith("```"):
            clean = clean.split("```")[1].replace("json", "").strip()
        parsed = json.loads(clean)
        route = parsed.get("route", "rag")
        reasoning = parsed.get("reasoning", "")
    except (json.JSONDecodeError, KeyError):
        route = "rag"  # Default seguro
        reasoning = "No se pudo parsear la clasificación. Default a RAG."
    
    if route not in ("rag", "tools", "web", "multi"):
        route = "rag"
    
    logger.info("router_decision", route=route, reasoning=reasoning[:100])
    
    return state.model_copy(update={
        "route": route,
        "route_reasoning": reasoning,
        "current_node": "router",
        "node_history": state.node_history + ["router"],
        "mermaid_log": state.mermaid_log + [{"node": "router", "status": "completed", "detail": route}]
    })
