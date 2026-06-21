"""FastAPI app principal — Evangelista Intelligence Platform."""
from contextlib import asynccontextmanager
from sqlalchemy import text
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

    try:
        from src.db.database import engine
        from src.db.models import Base
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            try:
                await conn.execute(text("ALTER TABLE projects ADD COLUMN IF NOT EXISTS status VARCHAR DEFAULT 'active' NOT NULL;"))
                await conn.execute(text("ALTER TABLE projects ADD COLUMN IF NOT EXISTS current_phase VARCHAR DEFAULT 'Scoping' NOT NULL;"))
                await conn.execute(text("ALTER TABLE projects ADD COLUMN IF NOT EXISTS total_price VARCHAR DEFAULT '0.00' NOT NULL;"))
                logger.info("Database migration: projects table columns verified.")
            except Exception as e:
                logger.warning(f"Database migration warning: {e}")
    except Exception as e:
        logger.error(f"Error initializing database tables: {e}")

    # Importar especialistas para disparar auto-registro
    from src.agents import registry  # noqa: F401

    # Asegurar que los agentes se carguen
    import src.agents.financial      # noqa: F401
    import src.agents.process        # noqa: F401
    import src.agents.data_engineer  # noqa: F401

    from src.agents.registry import AgentRegistry
    agents = AgentRegistry.list_agents()
    logger.info("agents_registered", agents=agents)

    try:
        from src.utils.qdrant import get_qdrant_client
        from src.retrieval.hybrid_retriever import HybridRetriever
        logger.info("Building BM25 index from Qdrant vault...")
        qdrant_client = get_qdrant_client()
        hybrid_retriever_instance = HybridRetriever(qdrant_client, settings.QDRANT_COLLECTION)
        await hybrid_retriever_instance._build_bm25_index()
        app.state.hybrid_retriever = hybrid_retriever_instance
        logger.info("BM25 index ready.")
    except Exception as e:
        logger.error("Error building BM25 index: " + str(e))

    yield

    logger.info("api_shutdown")
    close_qdrant_client()


app = FastAPI(
    title="Evangelista Intelligence Platform",
    version="1.0.0",
    description="Orquestador de agentes especialistas para consultoría estratégica.",
    lifespan=lifespan,
)

# ━━━ CORS Seguro — Orígenes autorizados ━━━
ALLOWED_ORIGINS = [
    # Producción (GitHub Pages)
    "https://gaec545-lang.github.io",
    "https://evangelistaco.com",
    "https://www.evangelistaco.com",
    
    # Desarrollo Local
    "http://localhost:5173",
    "http://localhost:5174",
    "http://localhost:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:5174",
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_origin_regex=r"https://.*\.azurecontainerapps\.io",
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
    ai_chat,
)
from src.api.routes import templates, notarial, auth_routes

from fastapi import Depends
from src.api.middleware.auth import verify_jwt




app.include_router(auth_routes.router, prefix="/api/v1/auth", tags=["Auth"])
app.include_router(health.router, tags=["Health"])
app.include_router(analyze.router, prefix="/api/v1", tags=["Analyze"], dependencies=[Depends(verify_jwt)])
app.include_router(graph_viz.router, prefix="/api/v1", tags=["Graph Visualization"], dependencies=[Depends(verify_jwt)])
app.include_router(agents.router, prefix="/api/v1", tags=["Agents"], dependencies=[Depends(verify_jwt)])
app.include_router(knowledge.router, prefix="/api/v1", tags=["Knowledge"], dependencies=[Depends(verify_jwt)])
app.include_router(proposals.router, prefix="/api/v1", tags=["Proposals"], dependencies=[Depends(verify_jwt)])
app.include_router(erp_connections.router, tags=["ERP Connections"], dependencies=[Depends(verify_jwt)])
app.include_router(team_management.router, tags=["Team"], dependencies=[Depends(verify_jwt)])
app.include_router(monte_carlo.router, tags=["Sentinel Monte Carlo"], dependencies=[Depends(verify_jwt)])
app.include_router(foundation_analysis.router, tags=["Foundation Analysis"], dependencies=[Depends(verify_jwt)])
app.include_router(documents.router, prefix="/api/v1", tags=["Documents"], dependencies=[Depends(verify_jwt)])
app.include_router(templates.router, tags=["Templates"], dependencies=[Depends(verify_jwt)])
app.include_router(client_files.router, tags=["Client Files"], dependencies=[Depends(verify_jwt)])
app.include_router(notarial.router, dependencies=[Depends(verify_jwt)])
app.include_router(ai_chat.router, prefix="/api/v1", tags=["AI Chat"], dependencies=[Depends(verify_jwt)])

from src.api.routes import db_crud
app.include_router(db_crud.router, dependencies=[Depends(verify_jwt)])

