from src.graph.state import GraphState, RetrievedDocument
import structlog

logger = structlog.get_logger()

async def web_search(state: GraphState) -> GraphState:
    """Busca información en internet usando DuckDuckGo."""
    query = state.refined_query or state.question
    
    try:
        from duckduckgo_search import DDGS
        
        with DDGS() as ddgs:
            results = list(ddgs.text(
                query + " México PyME empresa",
                max_results=5,
                region="mx-es"
            ))
        
        web_docs = [
            RetrievedDocument(
                id=f"web-{i}",
                title=r.get("title", "Sin título"),
                content=r.get("body", "")[:2000],
                source="web",
                score=0.7
            )
            for i, r in enumerate(results)
        ]
        
        logger.info("web_search_results", count=len(web_docs), query=query[:100])
        
    except Exception as e:
        logger.error("web_search_failed", error=str(e))
        web_docs = []
    
    return state.model_copy(update={
        "web_results": web_docs,
        "current_node": "web_searcher",
        "node_history": state.node_history + ["web_searcher"],
        "mermaid_log": state.mermaid_log + [{"node": "web_searcher", "status": "completed", "detail": f"{len(web_docs)} results"}]
    })
