from src.graph.state import GraphState

def decide_route(state: GraphState) -> str:
    """Post-router: decide a qué nodo ir."""
    if state.route == "rag":
        return "retriever"
    elif state.route == "tools":
        return "tool_executor"
    elif state.route == "web":
        return "web_searcher"
    elif state.route == "multi":
        return "retriever"
    return "retriever"
