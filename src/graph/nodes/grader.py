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

async def grade_documents(state: GraphState) -> dict:
    """CRAG: Evalúa la relevancia de cada documento recuperado."""
    if not state.documents:
        # ponytail: state update dictionary avoids Pydantic model copy overhead and node_history duplication
        return {
            "relevant_documents": [],
            "needs_web_search": True,
            "crag_action": "web_search",
            "current_node": "grader",
            "node_history": ["grader"],
            "mermaid_log": [{"node": "grader", "status": "completed", "detail": "0 relevant → web"}]
        }
    
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
    
    refined_query = None
    new_retry = state.retry_count
    if relevance_ratio >= 0.3:
        crag_action = "use_docs"
        needs_web = False
    elif relevance_ratio > 0:
        crag_action = "refine_query"
        needs_web = False
        new_retry += 1
        # ponytail: simple LLM query refinement to avoid repeating same results
        try:
            refine_prompt = f"Dado el siguiente problema y la baja relevancia de los resultados, reescribe la consulta para mejorar la búsqueda en la base de datos de conocimientos: {state.question}"
            refined_response = await llm.generate(
                prompt=refine_prompt,
                system_prompt="Responde solo con la nueva consulta de búsqueda.",
                temperature=0.2,
                max_tokens=60
            )
            refined_query = refined_response.strip().strip('"')
        except Exception:
            refined_query = state.question
    else:
        crag_action = "web_search"
        needs_web = True
    
    logger.info("crag_grading", 
                total=len(state.documents), 
                relevant=len(relevant_docs),
                ratio=f"{relevance_ratio:.2f}",
                action=crag_action)
    
    # ponytail: state update dictionary avoids Pydantic model copy overhead and node_history duplication
    return {
        "relevant_documents": relevant_docs,
        "needs_web_search": needs_web,
        "crag_action": crag_action,
        "refined_query": refined_query,
        "retry_count": new_retry,
        "current_node": "grader",
        "node_history": ["grader"],
        "mermaid_log": [{"node": "grader", "status": "completed", "detail": f"{len(relevant_docs)}/{len(state.documents)} relevant → {crag_action}"}]
    }
