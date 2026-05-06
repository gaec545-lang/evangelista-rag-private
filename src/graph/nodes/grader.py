from src.graph.state import GraphState
from src.llm.factory import get_llm_client
import json
import structlog

logger = structlog.get_logger()

GRADER_PROMPT = """Eres un evaluador de relevancia para Evangelista & Co.

Pregunta del usuario: {question}

Documento recuperado:
Título: {doc_title}
Contenido: {doc_content}

¿Este documento contiene información RELEVANTE para responder la pregunta?

Responde SOLO con JSON:
{{"relevant": true|false, "reasoning": "explicación corta"}}"""

async def grade_documents(state: GraphState) -> GraphState:
    """CRAG: Evalúa la relevancia de cada documento recuperado."""
    if not state.documents:
        return state.model_copy(update={
            "relevant_documents": [],
            "needs_web_search": True,
            "crag_action": "web_search",
            "current_node": "grader",
            "node_history": state.node_history + ["grader"],
            "mermaid_log": state.mermaid_log + [{"node": "grader", "status": "completed", "detail": "0 relevant → web"}]
        })
    
    # Usar modelo rápido para grading
    llm = get_llm_client()
    relevant_docs = []
    
    for doc in state.documents:
        response = await llm.generate(
            prompt=GRADER_PROMPT.format(
                question=state.question,
                doc_title=doc.title,
                doc_content=doc.content[:1500]
            ),
            system_prompt="",
            temperature=0.0,
            max_tokens=100
        )
        
        try:
            clean = response.strip()
            if clean.startswith("```"):
                clean = clean.split("```")[1].replace("json", "").strip()
            parsed = json.loads(clean)
            is_relevant = parsed.get("relevant", False)
            reasoning = parsed.get("reasoning", "")
        except (json.JSONDecodeError, KeyError):
            is_relevant = doc.score > 0.65  # Fallback
            reasoning = f"Fallback por score: {doc.score:.2f}"
        
        graded_doc = doc.model_copy(update={
            "relevant": is_relevant,
            "grader_reasoning": reasoning
        })
        
        if is_relevant:
            relevant_docs.append(graded_doc)
    
    # Decidir acción CRAG
    relevance_ratio = len(relevant_docs) / len(state.documents) if state.documents else 0
    
    if relevance_ratio >= 0.3:
        crag_action = "use_docs"
        needs_web = False
    elif relevance_ratio > 0:
        crag_action = "refine_query"
        needs_web = False
    else:
        crag_action = "web_search"
        needs_web = True
    
    logger.info("crag_grading", 
                total=len(state.documents), 
                relevant=len(relevant_docs),
                ratio=f"{relevance_ratio:.2f}",
                action=crag_action)
    
    return state.model_copy(update={
        "relevant_documents": relevant_docs,
        "needs_web_search": needs_web,
        "crag_action": crag_action,
        "current_node": "grader",
        "node_history": state.node_history + ["grader"],
        "mermaid_log": state.mermaid_log + [{"node": "grader", "status": "completed", "detail": f"{len(relevant_docs)}/{len(state.documents)} relevant → {crag_action}"}]
    })
