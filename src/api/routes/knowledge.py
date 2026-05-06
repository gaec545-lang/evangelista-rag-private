"""Routes de knowledge base: búsqueda e ingestión."""
from fastapi import APIRouter, HTTPException, Query
from src.api.schemas.requests import SearchRequest, SearchResponse
from src.utils.logger import get_logger

router = APIRouter()
logger = get_logger(__name__)


@router.post("/search", response_model=SearchResponse)
async def search_knowledge(request: SearchRequest):
    """Busca en el knowledge base. Aplica filtro de agente si se especifica."""
    from src.retrieval.query_engine import QueryEngine

    # "all" no es un agente válido para el filtro — usar el primero disponible o skip
    agent_name = request.agent
    if agent_name == "all":
        from src.agents.registry import AgentRegistry
        available = AgentRegistry.list_agents()
        agent_name = available[0] if available else "financial"

    logger.info("search_request", query=request.query[:80], agent=agent_name)

    try:
        engine = QueryEngine()
        results = await engine.search(
            query=request.query,
            agent_name=agent_name,
            final_k=request.top_k,
        )
    except Exception as e:
        logger.error("search_error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Error en búsqueda: {str(e)}")

    return SearchResponse(
        results=[r.model_dump() for r in results],
        total=len(results),
    )


@router.post("/ingest")
async def trigger_ingest(vault_path: str = Query(default=None)):
    """Dispara re-ingestión completa del vault."""
    from src.config import settings
    from src.ingestion.parser import MarkdownParser
    from src.ingestion.chunker import SemanticChunker
    from src.ingestion.embedder import Embedder
    from src.ingestion.indexer import Indexer

    path = vault_path or settings.VAULT_PATH
    logger.info("ingest_triggered", vault_path=path)

    try:
        parser = MarkdownParser()
        chunker = SemanticChunker()
        embedder = Embedder()
        indexer = Indexer()

        await indexer.ensure_collection()
        documents = parser.parse_directory(path)

        total_chunks = 0
        skipped = 0
        for doc in documents:
            stored_hash = indexer.get_document_hash(doc.id)
            if stored_hash == doc.file_hash:
                skipped += 1
                continue
            chunks = chunker.chunk(doc)
            chunks_with_embeddings = await embedder.embed_batch(chunks)
            await indexer.upsert_chunks(chunks_with_embeddings, doc)
            total_chunks += len(chunks_with_embeddings)

        stats = {
            "documents_processed": len(documents) - skipped,
            "documents_skipped": skipped,
            "chunks_indexed": total_chunks,
            "vault_path": path,
        }
        logger.info("ingest_complete", **stats)
        return {"status": "completed", "stats": stats}

    except Exception as e:
        logger.error("ingest_error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Error en ingestión: {str(e)}")
