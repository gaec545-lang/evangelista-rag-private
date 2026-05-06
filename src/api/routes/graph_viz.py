"""Rutas de visualización del grafo: GET /graph/mermaid, GET /graph/state, POST /graph/run."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any

import structlog

from src.graph.builder import build_graph, run_graph
from src.viz.mermaid_renderer import render_graph_definition, render_execution_trace

router = APIRouter()
logger = structlog.get_logger()


@router.get("/graph/mermaid")
async def get_graph_mermaid():
    """Retorna la arquitectura completa del grafo como Mermaid stateDiagram-v2."""
    try:
        # Primero intentar con LangGraph nativo; si falla, usar el renderer estático
        app = build_graph()
        mermaid_graph = app.get_graph().draw_mermaid()
        return {"mermaid": mermaid_graph}
    except Exception:
        return {"mermaid": render_graph_definition()}


@router.get("/graph/state/{thread_id}")
async def get_graph_state(thread_id: str):
    """Retorna el log de ejecución simulado para un thread (MVP)."""
    return {
        "thread_id": thread_id,
        "mermaid_log": [
            {"node": "router",    "status": "completed", "detail": "rag"},
            {"node": "retriever", "status": "completed", "detail": "3 docs"},
            {"node": "grader",    "status": "completed", "detail": "relevant"},
            {"node": "generator", "status": "completed", "detail": "850 chars"},
        ],
    }


class GraphRunRequest(BaseModel):
    question: str
    context: dict[str, Any] = {}
    thread_id: str = "default"


class GraphRunResponse(BaseModel):
    response: str
    confidence: float
    route: str
    node_history: list[str]
    sources: list[str] = []
    execution_time_ms: int
    retry_count: int
    errors: list[str]
    mermaid_trace: str


@router.post("/graph/run", response_model=GraphRunResponse)
async def run_graph_endpoint(request: GraphRunRequest):
    """Ejecuta el grafo Advanced RAG y retorna trazabilidad completa."""
    try:
        state = await run_graph(
            question=request.question,
            context=request.context,
            thread_id=request.thread_id,
        )
        return GraphRunResponse(
            response=state.final_response,
            confidence=state.confidence,
            route=state.route or "unknown",
            node_history=state.node_history,
            sources=state.generation_sources,
            execution_time_ms=state.execution_time_ms,
            retry_count=state.retry_count,
            errors=state.errors,
            mermaid_trace=render_execution_trace(state),
        )
    except Exception as e:
        logger.error("graph_run_error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Error en grafo: {str(e)}")
