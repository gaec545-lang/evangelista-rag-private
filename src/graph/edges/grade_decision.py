from src.graph.state import GraphState

def decide_after_grading(state: GraphState) -> str:
    """Post-CRAG: decide si generar, buscar en web, o refinar."""
    if state.crag_action == "use_docs":
        return "generator"
    elif state.crag_action == "web_search":
        return "web_searcher"
    elif state.crag_action == "refine_query":
        if state.retry_count < state.max_retries:
            return "retriever"
        return "generator"
    return "generator"
