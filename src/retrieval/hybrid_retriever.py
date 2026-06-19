from qdrant_client import QdrantClient
from qdrant_client.models import Prefetch, FusionQuery, Fusion
from typing import List
from dataclasses import dataclass
import asyncio
from .filters import build_agent_filter, build_client_filter, combine_filters

@dataclass
class RetrievedChunk:
    chunk_id: str
    document_id: str
    text: str
    score: float               # RRF score final
    metadata: dict             # metadata completa del chunk en Qdrant

class HybridRetriever:
    def __init__(self, qdrant_client: QdrantClient, embedder, collection_name: str = "evangelista_knowledge"):
        self.qdrant = qdrant_client
        self.embedder = embedder
        self.collection = collection_name
        # Assume FastEmbed or similar is generating sparse vectors if needed, 
        # or we just rely on Qdrant's sparse vector support via FastEmbed.
        
    async def _build_bm25_index(self):
        pass
        
    async def retrieve(
        self, 
        query: str, 
        agent_name: str,
        client_id: str, 
        top_k: int = 8
    ) -> List[RetrievedChunk]:
        """
        Ejecuta Búsqueda Híbrida (Densa + Dispersa) utilizando Qdrant nativo.
        Aplica filtro agent_access OBLIGATORIO en Qdrant.
        """
        # 1. Generar vector denso
        query_embedding = await self.embedder.embed_single(query) if hasattr(self.embedder, 'embed_single') else await self.embedder.embed(query)
        
        # 2. Generar vector disperso (asumiendo que el embedder tiene un método para esto, o Qdrant lo hace)
        # Si no lo tiene, FastEmbed en Qdrant client >= 1.9.0 soporta query() directo con texto para hybrid.
        
        agent_filter = build_agent_filter(agent_name)
        client_filter = build_client_filter(client_id)
        combined_filter = combine_filters(agent_filter, client_filter)
        
        # Usamos el modo de FastEmbed de qdrant_client o configuramos los prefetch.
        if hasattr(self.qdrant, "query"):
            # Si se usa fastembed integrado en QdrantClient (recomendado)
            results = self.qdrant.query(
                collection_name=self.collection,
                query_text=query,
                query_filter=combined_filter,
                limit=top_k
            )
        else:
            # Fallback manual con Prefetch usando los vectores
            # Asumimos que los vectores densos están en la tupla por defecto o con nombre.
            results = self.qdrant.query_points(
                collection_name=self.collection,
                prefetch=[
                    Prefetch(
                        query=query_embedding,
                        using="dense",
                        filter=combined_filter,
                        limit=top_k * 2
                    ),
                    Prefetch(
                        query=query, # Qdrant sparse vectors via BM25 model if integrated
                        using="sparse",
                        filter=combined_filter,
                        limit=top_k * 2
                    )
                ],
                query=FusionQuery(fusion=Fusion.RRF),
                limit=top_k
            ).points

        chunks = []
        for r in results:
            text = r.payload.get('content', r.payload.get('text', ''))
            chunks.append(RetrievedChunk(
                chunk_id=str(r.id),
                document_id=r.payload.get("document_id", ""),
                text=text,
                score=float(r.score),
                metadata=r.payload
            ))
            
        return chunks
