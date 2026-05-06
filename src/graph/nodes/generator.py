"""
Nodo Generator: Genera la respuesta final usando el contexto validado.
"""
from ..state import GraphState
from src.llm.factory import get_llm_client
import structlog

logger = structlog.get_logger()

GENERATOR_PROMPT = """Eres un consultor senior de Evangelista & Co., firma de Intelligence Architecture en Puebla, México.

Usa EXCLUSIVAMENTE la información proporcionada en el contexto para responder. Si el contexto no tiene suficiente información, dilo explícitamente — NO inventes datos.

## Contexto verificado

{context}

## Resultados de herramientas (si aplica)

{tool_results}

## Pregunta

{question}

## Instrucciones

1. Responde con datos concretos y cifras en MXN cuando sea posible
2. Cita las fuentes del contexto que usaste
3. Si calculas algo, muestra el paso a paso
4. Tono: directo, profesional, como consultor senior ante un Director General
5. NUNCA reveles fórmulas internas (α, β, Γ) en respuestas para clientes — Regla G-06"""

async def generate_response(state: GraphState) -> GraphState:
    """Genera respuesta con contexto verificado."""
    # Usar modelo de alta calidad para generación
    llm = get_llm_client()
    
    # Construir contexto desde documentos relevantes (CRAG-verified)
    docs_to_use = state.relevant_documents or state.documents
    all_docs = docs_to_use + state.web_results
    
    context_parts = []
    sources = []
    for doc in all_docs:
        label = "Knowledge Base" if doc.source == "qdrant" else "Web"
        context_parts.append(f"[{label}] {doc.title}\n{doc.content}")
        sources.append(f"{doc.title} ({doc.source})")
    
    # Inyectar contexto de sesión (notas, chat, etc.) si existe
    if state.context:
        if "notes" in state.context and state.context["notes"]:
            context_parts.append(f"[Session Notes]\n{state.context['notes']}")
        if "chat_history" in state.context and state.context["chat_history"]:
            context_parts.append(f"[Chat History]\n{state.context['chat_history']}")

    context = "\n\n---\n\n".join(context_parts) if context_parts else "No hay contexto disponible."
    
    # Tool results
    tool_str = ""
    if state.tool_results:
        tool_str = "\n".join([f"**{k}:** {v}" for k, v in state.tool_results.items()])
    
    response = await llm.generate(
        prompt=GENERATOR_PROMPT.format(
            context=context,
            tool_results=tool_str or "N/A",
            question=state.question
        ),
        system_prompt="",
        temperature=0.3,
        max_tokens=3000
    )
    
    logger.info("generator_complete", response_length=len(response), sources=len(sources))
    
    return state.model_copy(update={
        "generation": response,
        "generation_sources": sources,
        "current_node": "generator",
        "node_history": state.node_history + ["generator"],
        "mermaid_log": state.mermaid_log + [{"node": "generator", "status": "completed", "detail": f"{len(response)} chars"}]
    })
