"""FastAPI app principal — Evangelista Intelligence Platform."""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.utils.logger import get_logger
from src.utils.qdrant import close_qdrant_client
from src.config import settings

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: registrar agentes y verificar servicios. Shutdown: cleanup."""
    logger.info("api_startup")

    # Importar especialistas para disparar auto-registro
    from src.agents import registry  # noqa: F401

    # Asegurar que los agentes se carguen
    import src.agents.financial      # noqa: F401
    import src.agents.process        # noqa: F401
    import src.agents.data_engineer  # noqa: F401

    from src.agents.registry import AgentRegistry
    agents = AgentRegistry.list_agents()
    logger.info("agents_registered", agents=agents)

    yield

    logger.info("api_shutdown")
    close_qdrant_client()


app = FastAPI(
    title="Evangelista Intelligence Platform",
    version="1.0.0",
    description="Orquestador de agentes especialistas para consultoría estratégica.",
    lifespan=lifespan,
)

# ━━━ CORS estricto — sin wildcards ━━━
ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://localhost:5174",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:5174",
    "https://evangelistaco.com",
    "https://www.evangelistaco.com",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["x-document-folio", "Content-Disposition"],
    max_age=600,
)

# ━━━ Rate Limiting ━━━
from src.api.middleware.rate_limiting import RateLimitingMiddleware
app.add_middleware(RateLimitingMiddleware)

# ━━━ Request Logging ━━━
from src.api.middleware.logging import RequestLoggingMiddleware
app.add_middleware(RequestLoggingMiddleware)

# ━━━ Routes ━━━
from src.api.routes import (
    analyze,
    agents,
    knowledge,
    health,
    graph_viz,
    proposals,
    erp_connections,
    team_management,
    monte_carlo,
    foundation_analysis,
    documents,
    client_files,
)
from src.api.routes import templates

app.include_router(health.router, tags=["Health"])
app.include_router(analyze.router, prefix="/api/v1", tags=["Analyze"])
app.include_router(graph_viz.router, prefix="/api/v1", tags=["Graph Visualization"])
app.include_router(agents.router, prefix="/api/v1", tags=["Agents"])
app.include_router(knowledge.router, prefix="/api/v1", tags=["Knowledge"])
app.include_router(proposals.router, prefix="/api/v1", tags=["Proposals"])
app.include_router(erp_connections.router, tags=["ERP Connections"])
app.include_router(team_management.router, tags=["Team"])
app.include_router(monte_carlo.router, tags=["Sentinel Monte Carlo"])
app.include_router(foundation_analysis.router, tags=["Foundation Analysis"])
app.include_router(documents.router, prefix="/api/v1", tags=["Documents"])
app.include_router(templates.router, tags=["Templates"])
app.include_router(client_files.router, tags=["Client Files"])

