from rank_bm25 import BM25Okapi
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchAny
import asyncio
import numpy as np
from typing import List
from dataclasses import dataclass
from .filters import build_agent_filter

@dataclass
class RetrievedChunk:
    chunk_id: str
    document_id: str
    text: str
    score: float               # RRF score final
    semantic_score: float      # score original de Qdrant
    bm25_score: float          # score original de BM25 normalizado
    metadata: dict             # metadata completa del chunk en Qdrant

class HybridRetriever:
    
    def __init__(self, qdrant_client: QdrantClient, embedder, collection_name: str = "evangelista_knowledge"):
        self.qdrant = qdrant_client
        self.embedder = embedder
        self.collection = collection_name
        self._bm25_index = None
        self._bm25_corpus = []   # lista de (chunk_id, text)
        
    async def _build_bm25_index(self):
        """
        Construye índice BM25 en memoria sobre TODOS los chunks del vault.
        Se llama una vez al inicializar o si el vault se actualiza.
        Scrollea Qdrant en batches de 100 hasta recuperar todos los puntos.
        Tokeniza por espacios (tokenización simple, suficiente para español).
        """
        all_points = []
        offset = None
        while True:
            records, next_offset = self.qdrant.scroll(
                collection_name=self.collection,
                offset=offset,
                limit=100,
                with_payload=True
            )
            all_points.extend(records)
            if next_offset is None:
                break
            offset = next_offset
            
        self._bm25_corpus = [(str(point.id), point.payload.get('content', point.payload.get('text', ''))) for point in all_points]
        tokenized = [text.lower().split() for _, text in self._bm25_corpus]
        self._bm25_index = BM25Okapi(tokenized)
        
    async def retrieve(
        self, 
        query: str, 
        agent_name: str, 
        top_k: int = 8
    ) -> List[RetrievedChunk]:
        """
        Ejecuta BM25 + Qdrant en PARALELO y fusiona con RRF.
        Aplica filtro agent_access OBLIGATORIO en Qdrant (usar build_agent_filter existente).
        """
        
        # PASO 1: Construir índice BM25 si no existe
        if self._bm25_index is None:
            await self._build_bm25_index()
        
        # PASO 2: Ejecutar BM25 y Qdrant en paralelo
        bm25_task = asyncio.create_task(self._bm25_search(query, top_k=20))
        qdrant_task = asyncio.create_task(self._qdrant_search(query, agent_name, top_k=20))
        bm25_results, qdrant_results = await asyncio.gather(bm25_task, qdrant_task)
        
        # PASO 3: Aplicar RRF
        fused = self._reciprocal_rank_fusion(bm25_results, qdrant_results, k=60)
        
        return fused[:top_k]
    
    async def _bm25_search(self, query: str, top_k: int) -> List[tuple]:
        """
        Retorna lista de (chunk_id, normalized_score) ordenada por score desc.
        Normalizar score: bm25_scores / max(bm25_scores) para rango [0,1].
        """
        if not self._bm25_corpus:
            return []
            
        tokenized_query = query.lower().split()
        scores = self._bm25_index.get_scores(tokenized_query)
        top_indices = np.argsort(scores)[::-1][:top_k]
        results = []
        max_score = float(max(scores) + 1e-9) if len(scores) > 0 else 1.0
        for idx in top_indices:
            chunk_id, text = self._bm25_corpus[idx]
            normalized = float(scores[idx]) / max_score
            results.append((chunk_id, normalized, text))
        return results
    
    async def _qdrant_search(self, query: str, agent_name: str, top_k: int) -> List[tuple]:
        """
        Búsqueda semántica en Qdrant con filtro de seguridad obligatorio.
        Usar el embedder existente del proyecto para generar el embedding de la query.
        Retorna lista de (chunk_id, score, payload).
        Aplicar: build_agent_filter(agent_name) como filter param.
        """
        query_embedding = await self.embedder.embed(query)
        agent_filter = build_agent_filter(agent_name)
        
        results = self.qdrant.search(
            collection_name=self.collection,
            query_vector=query_embedding,
            query_filter=agent_filter,
            limit=top_k,
            with_payload=True
        )
        
        return [(str(r.id), float(r.score), r.payload) for r in results]
    
    def _reciprocal_rank_fusion(
        self, 
        bm25_results: List[tuple], 
        qdrant_results: List[tuple], 
        k: int = 60
    ) -> List[RetrievedChunk]:
        """
        RRF score: para cada chunk, sumar 1/(k + rank) de cada lista donde aparezca.
        chunk_id como clave de unión entre ambas listas.
        Retornar lista de RetrievedChunk ordenada por rrf_score desc.
        
        Fórmula: rrf_score(chunk) = Σ [ 1 / (k + rank_i) ] para cada lista i
        """
        scores = {}
        
        for rank, (chunk_id, bm25_score, text) in enumerate(bm25_results):
            if chunk_id not in scores:
                scores[chunk_id] = {"rrf": 0.0, "bm25": bm25_score, "semantic": 0.0, "text": text, "metadata": {}}
            scores[chunk_id]["rrf"] += 1.0 / (k + rank + 1)
        
        for rank, (chunk_id, semantic_score, payload) in enumerate(qdrant_results):
            text = payload.get('content', payload.get('text', ''))
            if chunk_id not in scores:
                scores[chunk_id] = {"rrf": 0.0, "bm25": 0.0, "semantic": semantic_score, "text": text, "metadata": payload}
            scores[chunk_id]["rrf"] += 1.0 / (k + rank + 1)
            scores[chunk_id]["semantic"] = semantic_score
            scores[chunk_id]["metadata"] = payload
            if scores[chunk_id]["text"] == "":
                 scores[chunk_id]["text"] = text
        
        sorted_chunks = sorted(scores.items(), key=lambda x: x[1]["rrf"], reverse=True)
        
        return [
            RetrievedChunk(
                chunk_id=cid,
                document_id=data["metadata"].get("document_id", ""),
                text=data["text"],
                score=data["rrf"],
                semantic_score=data["semantic"],
                bm25_score=data["bm25"],
                metadata=data["metadata"]
            )
            for cid, data in sorted_chunks
        ]
