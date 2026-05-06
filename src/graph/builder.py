"""
Builder del grafo Advanced RAG para Evangelista Intelligence Platform.

Flujo principal:
    router → retriever → grader ──(relevant)──→ generator → hallucination_check → quality_check → synthesizer → END
                                 ↓(web_search)
                            web_searcher ──────→ generator
                                 ↓(refine)
                            retriever (retry)
    router → tool_executor ────────────────────→ generator
    router → web_searcher ─────────────────────→ generator
"""
import time
from langgraph.graph import StateGraph, END
from .state import GraphState
import structlog

logger = structlog.get_logger(__name__)

# ─── Nodos ────────────────────────────────────────────────────────────────────
from .nodes.router import route_question
from .nodes.retriever import retrieve_documents
from .nodes.grader import grade_documents
from .nodes.web_searcher import web_search
from .nodes.tool_executor import execute_tools
from .nodes.generator import generate_response
from .nodes.hallucination_check import check_hallucination
from .nodes.quality_check import check_quality
from .nodes.synthesizer import synthesize

# ─── Aristas condicionales ────────────────────────────────────────────────────
from .edges.route_decision import decide_route
from .edges.grade_decision import decide_after_grading
from .edges.hallucination_decision import decide_after_hallucination
from .edges.quality_decision import decide_after_quality


def build_graph():
    """Construye y compila el grafo LangGraph de Advanced RAG."""
    workflow = StateGraph(GraphState)

    # Nodos
    workflow.add_node("router",             route_question)
    workflow.add_node("retriever",          retrieve_documents)
    workflow.add_node("grader",             grade_documents)
    workflow.add_node("web_searcher",       web_search)
    workflow.add_node("tool_executor",      execute_tools)
    workflow.add_node("generator",          generate_response)
    workflow.add_node("hallucination_check", check_hallucination)
    workflow.add_node("quality_check",      check_quality)
    workflow.add_node("synthesizer",        synthesize)

    # Entry point
    workflow.set_entry_point("router")

    # Router → rama RAG / Tools / Web
    workflow.add_conditional_edges(
        "router",
        decide_route,
        {
            "retriever":     "retriever",
            "tool_executor": "tool_executor",
            "web_searcher":  "web_searcher",
        },
    )

    # RAG: retriever → grader → (CRAG decision)
    workflow.add_edge("retriever", "grader")
    workflow.add_conditional_edges(
        "grader",
        decide_after_grading,
        {
            "generator":    "generator",
            "web_searcher": "web_searcher",
            "retriever":    "retriever",
        },
    )

    # Web y Tools convergen en generator
    workflow.add_edge("web_searcher",  "generator")
    workflow.add_edge("tool_executor", "generator")

    # Self-Reflective RAG
    workflow.add_edge("generator", "hallucination_check")
    workflow.add_conditional_edges(
        "hallucination_check",
        decide_after_hallucination,
        {
            "quality_check": "quality_check",
            "generator":     "generator",
            "synthesizer":   "synthesizer",
        },
    )
    workflow.add_conditional_edges(
        "quality_check",
        decide_after_quality,
        {
            "synthesizer": "synthesizer",
            "generator":   "generator",
        },
    )

    workflow.add_edge("synthesizer", END)

    return workflow.compile()


# ─── Alias para backward compat con orchestrator/ ────────────────────────────
create_graph = build_graph


async def run_graph(
    question: str,
    context: "dict | None" = None,
    thread_id: str = "default",
) -> GraphState:
    """Punto de entrada principal del Advanced RAG."""
    logger.info("graph_start", question=question[:80], thread_id=thread_id)
    start = time.time()

    compiled = build_graph()
    initial_state = GraphState(
        question=question,
        context=context or {},
        thread_id=thread_id,
    )

    raw = await compiled.ainvoke(initial_state)

    # LangGraph puede retornar dict o GraphState — normalizar siempre a GraphState
    final: GraphState = GraphState(**raw) if isinstance(raw, dict) else raw  # type: ignore[assignment]

    elapsed = int((time.time() - start) * 1000)
    object.__setattr__(final, "execution_time_ms", elapsed)  # evita re-validación Pydantic

    logger.info(
        "graph_complete",
        confidence=final.confidence,
        nodes=len(final.node_history),
        time_ms=elapsed,
    )
    return final
