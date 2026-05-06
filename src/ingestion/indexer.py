"""Indexación de chunks en Qdrant con metadata completa."""
from qdrant_client import QdrantClient
from qdrant_client.models import (
    VectorParams,
    Distance,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
    PayloadSchemaType,
)
from qdrant_client.http.exceptions import UnexpectedResponse

from src.core.models import Chunk
from src.utils.logger import get_logger
from src.config import settings
from src.utils.qdrant import get_qdrant_client

logger = get_logger(__name__)


class Indexer:
    """Gestiona el upsert de chunks a Qdrant con detección de cambios."""

    def __init__(
        self,
        collection: str = settings.QDRANT_COLLECTION,
        vector_size: int = settings.EMBED_DIMENSIONS,
    ) -> None:
        self._client = None
        self.collection = collection
        self.vector_size = vector_size

    @property
    def client(self):
        if self._client is None:
            self._client = get_qdrant_client()
        return self._client

    def ensure_collection(self) -> None:
        """Crea la colección en Qdrant si no existe, con índices de payload."""
        try:
            self.client.get_collection(self.collection)
            logger.info("coleccion_existente", collection=self.collection)
        except (UnexpectedResponse, Exception):
            logger.info("creando_coleccion", collection=self.collection)
            self.client.create_collection(
                collection_name=self.collection,
                vectors_config=VectorParams(size=self.vector_size, distance=Distance.COSINE),
            )
            # Crear índices de payload para filtrado rápido
            for field in ("agent_access", "domain", "sector", "type", "tags"):
                self.client.create_payload_index(
                    collection_name=self.collection,
                    field_name=field,
                    field_schema=PayloadSchemaType.KEYWORD,
                )
            logger.info("indices_creados", collection=self.collection)

    def get_document_hash(self, document_id: str) -> str | None:
        """Retorna el file_hash del primer chunk de un documento (si existe)."""
        try:
            results = self.client.scroll(
                collection_name=self.collection,
                scroll_filter=Filter(
                    must=[FieldCondition(key="document_id", match=MatchValue(value=document_id))]
                ),
                limit=1,
                with_payload=True,
            )
            points = results[0]
            if points:
                return points[0].payload.get("file_hash")
        except Exception as e:
            logger.warning("error_obteniendo_hash", doc_id=document_id, error=str(e))
        return None

    def delete_document(self, document_id: str) -> int:
        """Elimina todos los chunks de un documento. Retorna cantidad eliminada."""
        try:
            self.client.delete(
                collection_name=self.collection,
                points_selector=Filter(
                    must=[FieldCondition(key="document_id", match=MatchValue(value=document_id))]
                ),
            )
            logger.info("chunks_eliminados", doc_id=document_id)
            return 1
        except Exception as e:
            logger.error("error_eliminando_documento", doc_id=document_id, error=str(e))
            return 0

    def upsert_chunks(self, chunks: list[Chunk]) -> bool:
        """
        Indexa una lista de chunks en Qdrant.
        Verifica si el documento cambió (por file_hash) antes de re-indexar.
        Retorna True si se indexó, False si era igual y se saltó.
        """
        if not chunks:
            return False

        document_id = chunks[0].document_id
        new_hash = chunks[0].file_hash

        existing_hash = self.get_document_hash(document_id)
        if existing_hash == new_hash:
            logger.info("documento_sin_cambios", doc_id=document_id)
            return False

        if existing_hash is not None:
            self.delete_document(document_id)

        points = [
            PointStruct(
                id=str(chunk.chunk_id),
                vector=chunk.embedding,
                payload={
                    "chunk_id": chunk.chunk_id,
                    "document_id": chunk.document_id,
                    "document_title": chunk.document_title,
                    "section_header": chunk.section_header,
                    "content": chunk.content,
                    "type": chunk.type,
                    "domain": chunk.domain,
                    "sector": chunk.sector,
                    "agent_access": chunk.agent_access,
                    "confidence": chunk.confidence,
                    "source": chunk.source,
                    "tags": chunk.tags,
                    "chunk_index": chunk.chunk_index,
                    "total_chunks": chunk.total_chunks,
                    "file_hash": chunk.file_hash,
                },
            )
            for chunk in chunks
        ]

        self.client.upsert(collection_name=self.collection, points=points)
        logger.info("chunks_indexados", doc_id=document_id, total=len(chunks))
        return True

    def collection_stats(self) -> dict:
        """Retorna estadísticas de la colección."""
        try:
            info = self.client.get_collection(self.collection)
            return {
                "collection": self.collection,
                "total_points": info.points_count,
                "status": info.status,
                "vector_size": info.config.params.vectors.size,
            }
        except Exception as e:
            return {"error": str(e)}
