import structlog
from qdrant_client.models import Filter

from src.core.models import SearchResult
from src.ingestion.embedder import Embedder
from src.retrieval.filters import (
    build_agent_filter,
    build_domain_filter,
    combine_filters,
)
from src.config import settings
from src.utils.qdrant import get_qdrant_client

logger = structlog.get_logger()

class QueryEngine:
    """
    Motor de búsqueda RAG con filtros de seguridad por agente.
    Cada búsqueda aplica el filtro de agent_access OBLIGATORIAMENTE.
    """

    def __init__(
        self,
        embedder: Embedder | None = None,
        collection: str = settings.QDRANT_COLLECTION,
    ) -> None:
        self._client = None
        self.collection = collection
        self.embedder = embedder or Embedder()
        self.settings = settings

    @property
    def client(self):
        if self._client is None:
            self._client = get_qdrant_client()
        return self._client

    @client.setter
    def client(self, value):
        self._client = value

    async def search(
        self,
        query: str,
        agent_name: str,
        domain_filter: list[str] | None = None,
        sector_filter: list[str] | None = None,
        type_filter: list[str] | None = None,
        top_k: int = 10,
        final_k: int = 5
    ) -> list[SearchResult]:
        
        logger.info("rag_search_start", query=query[:100], agent=agent_name, top_k=top_k)
        
        try:
            # 1. Generar embedding de la query
            query_embedding = await self.embedder.embed_single(query)
            logger.info("rag_embedding_generated", dimensions=len(query_embedding))
            
            # 2. Construir filtros
            filters = [build_agent_filter(agent_name)]
            if domain_filter:
                filters.append(build_domain_filter(domain_filter))
            
            combined = combine_filters(*filters) if len(filters) > 1 else filters[0]
            
            # 3. Buscar en Qdrant (Compatibilidad >=1.10 y anteriores)
            if hasattr(self.client, "query_points"):
                response = self.client.query_points(
                    collection_name=self.collection,
                    query=query_embedding,
                    query_filter=combined,
                    limit=top_k
                )
                results = response.points
            else:
                # Fallback para versiones antiguas de qdrant-client
                results = self.client.search(
                    collection_name=self.collection,
                    query_vector=query_embedding,
                    query_filter=combined,
                    limit=top_k
                )
            
            logger.info("rag_search_results", count=len(results), agent=agent_name)
            
            if not results:
                logger.warning("rag_search_empty", query=query[:100], agent=agent_name, 
                             message="No se encontraron chunks. Verificar que la colección está poblada y los filtros son correctos.")
                return []
            
            # 4. Convertir a SearchResult
            search_results = []
            for r in results[:final_k]:
                sr = SearchResult(
                    chunk_id=r.payload.get("chunk_id", ""),
                    document_id=r.payload.get("document_id", ""),
                    document_title=r.payload.get("document_title", "Sin título"),
                    section_header=r.payload.get("section_header", ""),
                    content=r.payload.get("content", ""),
                    score=r.score,
                    metadata={
                        "type": r.payload.get("type"),
                        "domain": r.payload.get("domain"),
                        "tags": r.payload.get("tags"),
                    }
                )
                search_results.append(sr)
            
            logger.info("rag_search_complete", 
                       final_count=len(search_results), 
                       top_score=search_results[0].score if search_results else 0,
                       top_doc=search_results[0].document_title if search_results else "none")
            
            return search_results
            
        except Exception as e:
            logger.error("rag_search_failed", error=str(e), query=query[:100], agent=agent_name)
            # NO fallar silenciosamente — retornar lista vacía pero con log
            return []

    def format_context(self, results: list[SearchResult]) -> str:
        """Formatea los resultados como contexto para el LLM."""
        if not results:
            return "No se encontraron documentos relevantes en la base de conocimiento."

        parts = []
        for i, r in enumerate(results, 1):
            parts.append(
                f"[Fuente {i}] {r.document_title} — {r.section_header}\n"
                f"(Score: {r.score:.3f})\n\n"
                f"{r.content}"
            )
        return "\n\n---\n\n".join(parts)
