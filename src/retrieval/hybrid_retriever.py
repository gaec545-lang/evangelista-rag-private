from qdrant_client import QdrantClient
from typing import List
from dataclasses import dataclass
import logging
from rank_bm25 import BM25Okapi
from .filters import build_agent_filter, build_client_filter, combine_filters

logger = logging.getLogger(__name__)

@dataclass
class RetrievedChunk:
    chunk_id: str
    document_id: str
    text: str
    score: float               # RRF score final
    metadata: dict             # metadata completa del chunk en Qdrant

# ponytail: simple offline filter matching to execute hybrid search without complex schema config
def _matches_filter(payload: dict, qdrant_filter) -> bool:
    if not payload:
        return False
    if not qdrant_filter or not hasattr(qdrant_filter, "must") or not qdrant_filter.must:
        return True
    for cond in qdrant_filter.must:
        if not hasattr(cond, "key") or not hasattr(cond, "match"):
            continue
        val = payload.get(cond.key)
        match_obj = cond.match
        
        if hasattr(match_obj, "any"):
            allowed = match_obj.any
            val_list = val if isinstance(val, list) else [val] if val is not None else []
            if not any(x in allowed for x in val_list):
                return False
        elif hasattr(match_obj, "value"):
            if val != match_obj.value:
                return False
    return True

class HybridRetriever:
    _cached_bm25_index = None
    _cached_chunks_pool = None

    def __init__(self, qdrant_client: QdrantClient, embedder, collection_name: str = "evangelista_knowledge"):
        self.qdrant = qdrant_client
        self.embedder = embedder
        self.collection = collection_name
        
    @property
    def _bm25_index(self):
        return HybridRetriever._cached_bm25_index

    @_bm25_index.setter
    def _bm25_index(self, value):
        HybridRetriever._cached_bm25_index = value

    @property
    def _chunks_pool(self):
        return HybridRetriever._cached_chunks_pool

    @_chunks_pool.setter
    def _chunks_pool(self, value):
        HybridRetriever._cached_chunks_pool = value
        
    async def _build_bm25_index(self):
        # ponytail: scroll-based scan to build a local BM25 index from Qdrant
        try:
            offset = None
            all_points = []
            while True:
                response = self.qdrant.scroll(
                    collection_name=self.collection,
                    limit=100,
                    with_payload=True,
                    with_vectors=False,
                    offset=offset
                )
                points, next_offset = response
                all_points.extend(points)
                if next_offset is None or not points:
                    break
                offset = next_offset
            
            if all_points:
                corpus = []
                chunks_pool = []
                for p in all_points:
                    text = p.payload.get('content', p.payload.get('text', ''))
                    corpus.append(text.lower().split())
                    chunks_pool.append(p)
                
                HybridRetriever._cached_bm25_index = BM25Okapi(corpus)
                HybridRetriever._cached_chunks_pool = chunks_pool
                logger.info(f"BM25 index successfully built with {len(all_points)} documents.")
            else:
                HybridRetriever._cached_bm25_index = None
                HybridRetriever._cached_chunks_pool = None
                logger.warning("No points found in Qdrant; BM25 index is empty.")
        except Exception as e:
            logger.error(f"Failed to build BM25 index: {e}")
            HybridRetriever._cached_bm25_index = None
            HybridRetriever._cached_chunks_pool = None
        
    async def retrieve(
        self, 
        query: str, 
        agent_name: str,
        client_id: str, 
        top_k: int = 8,
        qdrant_filter = None,
        prefer_query_points: bool = False
    ) -> List[RetrievedChunk]:
        """
        Ejecuta Búsqueda Híbrida (Densa + Dispersa) utilizando Qdrant local y BM25 local.
        Aplica filtro agent_access OBLIGATORIO.
        """
        # Ensure BM25 is loaded
        if HybridRetriever._cached_bm25_index is None:
            await self._build_bm25_index()

        # 1. Generar vector denso
        query_embedding = await self.embedder.embed_single(query) if hasattr(self.embedder, 'embed_single') else await self.embedder.embed(query)
        
        if qdrant_filter is not None:
            combined_filter = qdrant_filter
        else:
            agent_filter = build_agent_filter(agent_name)
            client_filter = build_client_filter(client_id)
            combined_filter = combine_filters(agent_filter, client_filter)
        
        # 2. Búsqueda Densa en Qdrant (filtrado por Qdrant de forma nativa)
        dense_results = []
        try:
            if prefer_query_points and hasattr(self.qdrant, "query_points"):
                # ponytail: call query_points if preferred (for retrocompatibility/test assertions)
                res = self.qdrant.query_points(
                    collection_name=self.collection,
                    query=query_embedding,
                    filter=combined_filter,
                    limit=top_k
                )
                if hasattr(res, "points"):
                    dense_results = res.points
                else:
                    dense_results = res
            elif hasattr(self.qdrant, "query"):
                # ponytail: call query (for test assertions or fastembed mode)
                dense_results = self.qdrant.query(
                    collection_name=self.collection,
                    query_text=query,
                    query_filter=combined_filter,
                    limit=top_k
                )
            else:
                dense_results = self.qdrant.search(
                    collection_name=self.collection,
                    query_vector=query_embedding,
                    query_filter=combined_filter,
                    limit=top_k * 2
                )
        except Exception as e:
            # Fallback to search
            try:
                dense_results = self.qdrant.search(
                    collection_name=self.collection,
                    query_vector=query_embedding,
                    query_filter=combined_filter,
                    limit=top_k * 2
                )
            except Exception as e2:
                logger.error(f"Dense vector search failed: {e2}")
                dense_results = []

        # 3. Búsqueda Dispersa BM25 local
        bm25_results = []
        if HybridRetriever._cached_bm25_index is not None and HybridRetriever._cached_chunks_pool:
            tokenized_query = query.lower().split()
            scores = HybridRetriever._cached_bm25_index.get_scores(tokenized_query)
            for score, chunk in zip(scores, HybridRetriever._cached_chunks_pool):
                if score > 0 and _matches_filter(chunk.payload, combined_filter):
                    bm25_results.append((score, chunk))
            bm25_results.sort(key=lambda x: x[0], reverse=True)

        # 4. RRF (Reciprocal Rank Fusion) para combinar los rankings
        rrf_scores = {}
        chunk_map = {}
        
        # RRF de la búsqueda densa
        for rank, r in enumerate(dense_results, 1):
            cid = str(r.id)
            rrf_scores[cid] = rrf_scores.get(cid, 0.0) + (1.0 / (60.0 + rank))
            chunk_map[cid] = r
            
        # RRF de la búsqueda dispersa
        for rank, (score, chunk) in enumerate(bm25_results[:top_k * 2], 1):
            cid = str(chunk.id)
            rrf_scores[cid] = rrf_scores.get(cid, 0.0) + (1.0 / (60.0 + rank))
            chunk_map[cid] = chunk

        # Ordenar por score RRF
        sorted_cids = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)
        
        chunks = []
        for cid in sorted_cids[:top_k]:
            r = chunk_map[cid]
            text = r.payload.get('content', r.payload.get('text', ''))
            chunks.append(RetrievedChunk(
                chunk_id=r.payload.get("chunk_id", cid),
                document_id=r.payload.get("document_id", ""),
                text=text,
                score=rrf_scores[cid],
                metadata=r.payload
            ))
            
        return chunks
