"""Route del orquestador: POST /api/v1/analyze."""
from fastapi import APIRouter, HTTPException
from src.graph.builder import run_graph
from src.viz.mermaid_renderer import render_execution_trace
from src.api.schemas.requests import AnalyzeRequest, AnalyzeResponse
from src.utils.logger import get_logger

router = APIRouter()
logger = get_logger(__name__)


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze(request: AnalyzeRequest):
    """Ejecuta el grafo de Advanced RAG y retorna la respuesta sintetizada."""
    logger.info("analyze_request_graph", task=request.task[:80])

    try:
        state = await run_graph(
            question=request.task,
            context=request.context,
        )

        return AnalyzeResponse(
            status="completed",
            response=state.final_response,
            confidence=state.confidence,
            sources=state.generation_sources,
            route=state.route or "unknown",
            node_history=state.node_history,
            execution_time_ms=state.execution_time_ms,
            retry_count=state.retry_count,
            errors=state.errors,
            subtasks=[],
            mermaid_trace=render_execution_trace(state),
        )
    except Exception as e:
        logger.error("graph_execution_error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Error en ejecución de grafo: {str(e)}")
