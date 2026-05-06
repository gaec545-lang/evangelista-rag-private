"""Routes de agentes: lista y ejecución directa."""
from fastapi import APIRouter, HTTPException
from src.api.schemas.requests import AgentExecuteRequest, AgentExecuteResponse
from src.utils.logger import get_logger

router = APIRouter()
logger = get_logger(__name__)


@router.get("/agents")
async def list_agents():
    """Lista todos los agentes registrados con sus dominios y herramientas."""
    from src.agents.registry import AgentRegistry
    agents = AgentRegistry.list_agents()
    details = []
    for name in agents:
        agent = AgentRegistry.get(name)
        details.append({
            "name": name,
            "domains": agent.domains,
            "tools": agent.tools,
        })
    return {"agents": details, "total": len(details)}


@router.post("/agents/{name}/execute", response_model=AgentExecuteResponse)
async def execute_agent(name: str, request: AgentExecuteRequest):
    """Ejecuta un agente individual directamente (bypass del orquestador)."""
    from src.agents.registry import AgentRegistry

    try:
        agent = AgentRegistry.get(name)
    except ValueError:
        available = AgentRegistry.list_agents()
        raise HTTPException(
            status_code=404,
            detail=f"Agente '{name}' no encontrado. Disponibles: {available}",
        )

    logger.info("direct_agent_execute", agent=name, task=request.task[:80])

    try:
        result = await agent.execute(request.task, context=request.context or None)
    except Exception as e:
        logger.error("agent_execute_error", agent=name, error=str(e))
        raise HTTPException(status_code=500, detail=f"Error ejecutando agente '{name}': {str(e)}")

    return AgentExecuteResponse(
        agent=name,
        confidence=result.confidence,
        analysis=result.analysis,
        recommendations=result.recommendations,
        sources=result.sources_used,
        escalation=result.escalation_needed,
        escalation_reason=result.escalation_reason,
    )
