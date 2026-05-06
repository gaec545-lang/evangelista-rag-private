"""Health y readiness checks."""
from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health():
    """Health check básico — siempre devuelve 200 si la API está corriendo."""
    return {"status": "healthy", "service": "evangelista-intelligence-platform"}


@router.get("/readiness")
async def readiness():
    """Readiness check: verifica Qdrant, LLM y agentes registrados."""
    checks: dict = {}

    # Qdrant
    try:
        from src.utils.qdrant import get_qdrant_client
        client = get_qdrant_client()
        collections = client.get_collections()
        checks["qdrant"] = {"status": "ready", "collections": len(collections.collections)}
    except Exception as e:
        checks["qdrant"] = {"status": "not_ready", "error": str(e)}

    # LLM
    try:
        from src.llm.factory import get_llm_client
        from src.config import settings
        llm = get_llm_client()
        checks["llm"] = {"status": "ready", "provider": settings.LLM_PROVIDER, "client": type(llm).__name__}
    except Exception as e:
        checks["llm"] = {"status": "not_ready", "error": str(e)}

    # Agentes
    try:
        from src.agents.registry import AgentRegistry
        agents = AgentRegistry.list_agents()
        checks["agents"] = {"status": "ready", "count": len(agents), "names": agents}
    except Exception as e:
        checks["agents"] = {"status": "not_ready", "error": str(e)}

    all_ready = all(c.get("status") == "ready" for c in checks.values())
    status_code = 200 if all_ready else 503

    from fastapi import Response
    from fastapi.responses import JSONResponse
    return JSONResponse(
        content={"ready": all_ready, "checks": checks},
        status_code=status_code,
    )
