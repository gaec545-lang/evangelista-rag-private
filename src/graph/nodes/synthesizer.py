from src.graph.state import GraphState
import structlog

logger = structlog.get_logger()

async def synthesize(state: GraphState) -> GraphState:
    """Prepara la respuesta final con metadata."""
    # Calcular confianza basada en el recorrido del grafo
    confidence = 0.5  # Base
    
    if state.hallucination_check:
        confidence += 0.2
    if state.quality_check:
        confidence += 0.2
    
    if state.relevant_documents:
        avg_score = sum(d.score for d in state.relevant_documents) / len(state.relevant_documents)
        confidence += avg_score * 0.1
    
    confidence = min(1.0, confidence)
    
    # Construir respuesta final
    final = state.generation
    
    # Agregar fuentes si hay
    if state.generation_sources:
        sources_list = list(set(state.generation_sources))
        final += "\n\n---\n**Fuentes consultadas:** " + ", ".join(sources_list[:8])
    
    # Agregar advertencias si hubo correcciones
    warnings = []
    if state.retry_count > 0:
        warnings.append(f"Se requirieron {state.retry_count} correcciones para verificar la respuesta.")
    if state.web_results:
        warnings.append("Parte de la información proviene de búsqueda web (no del knowledge base interno).")
    
    if warnings:
        final += "\n\n**Advertencias:** " + " | ".join(warnings)
    
    logger.info("synthesis_complete", confidence=f"{confidence:.2f}")
    
    return state.model_copy(update={
        "final_response": final,
        "confidence": confidence,
        "current_node": "synthesizer",
        "node_history": state.node_history + ["synthesizer"],
        "mermaid_log": state.mermaid_log + [{"node": "synthesizer", "status": "completed", "detail": f"confidence={confidence:.2f}"}]
    })
