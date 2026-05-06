"""
Nodo Web Searcher: Busca en internet cuando CRAG detecta que el knowledge
base no tiene información relevante, o cuando el Router clasifica la
pregunta como "web".

Usa DuckDuckGo (sin API key) con fallback graceful si no está instalado.
"""
from __future__ import annotations

from ..state import GraphState, RetrievedDocument, NodeStatus
import structlog

logger = structlog.get_logger()

_MX_CONTEXT = "México empresa PyME"


async def web_search(state: GraphState) -> GraphState:
    """Busca en DuckDuckGo y devuelve hasta 5 resultados como RetrievedDocument."""
    query = state.refined_query or state.question
    search_query = f"{query} {_MX_CONTEXT}"

    web_docs: list[RetrievedDocument] = []
    new_errors = list(state.errors)

    try:
        from duckduckgo_search import DDGS  # type: ignore[import]

        with DDGS() as ddgs:
            raw_results = list(
                ddgs.text(search_query, max_results=5, region="mx-es")
            )

        web_docs = [
            RetrievedDocument(
                id=f"web-{i}",
                title=r.get("title", "Sin título"),
                content=(r.get("body") or "")[:2000],
                source="web",
                score=0.70,
            )
            for i, r in enumerate(raw_results)
            if r.get("body")
        ]

        logger.info("web_search_ok", count=len(web_docs), query=query[:100])

    except ImportError:
        logger.warning("web_search_unavailable", reason="duckduckgo-search not installed")
    except Exception as exc:
        logger.error("web_search_failed", error=str(exc))
        new_errors.append(f"web_search: {exc}")

    return state.model_copy(update={
        "web_results": web_docs,
        "errors": new_errors,
        "current_node": "web_searcher",
        "node_history": state.node_history + ["web_searcher"],
        "mermaid_log": state.mermaid_log + [
            state.log_node("web_searcher", NodeStatus.COMPLETED, f"{len(web_docs)} results")
        ],
    })
