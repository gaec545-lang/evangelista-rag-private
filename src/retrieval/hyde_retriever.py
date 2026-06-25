import logging
import asyncio
from typing import List
from qdrant_client import QdrantClient
from .filters import build_agent_filter, build_client_filter, combine_filters
from .hybrid_retriever import RetrievedChunk
from src.llm.ollama_client import OllamaClient
from src.config import settings

logger = logging.getLogger(__name__)

class HyDERetriever:
    
    HYDE_PROMPT_TEMPLATE = """Eres un consultor senior de Evangelista & Co., firma de consultoría de inteligencia de negocios en México especializada en diagnóstico financiero forense, reestructuración operativa y automatización de procesos para empresas manufactureras y PyMEs.

Escribe el fragmento de una metodología interna de Evangelista & Co. que respondería exactamente esta pregunta de un consultor junior:

Pregunta: {query}

REGLAS:
- Máximo 150 palabras
- Tono técnico y corporativo
- Sin preámbulo ni "Claro, aquí va..."
- Escribe directamente el contenido metodológico
- Usa terminología de consultoría (frameworks, fórmulas, pasos concretos)

Fragmento metodológico:"""

    def __init__(self, qdrant_client, embedder, collection_name: str = "evangelista_knowledge"):
        self.qdrant = qdrant_client
        self.embedder = embedder
        self.collection = collection_name
        self.ollama_client = OllamaClient(base_url=settings.OLLAMA_BASE_URL, model=settings.HYDE_MODEL)
    
    async def retrieve(
        self,
        query: str,
        agent_name: str,
        client_id: str,
        top_k: int = 8
    ) -> List[RetrievedChunk]:
        """
        1. Genera documento hipotético con Ollama
        2. Embeds el documento hipotético (NO la query)
        3. Busca en Qdrant usando ese embedding + filtro agent_access
        4. Si Ollama falla o timeout (>5s) → retorna [] para activar fallback Hybrid
        """
        try:
            # PASO 1: Generar hipótesis
            hypothesis = await self._generate_hypothesis(query)
            
            if not hypothesis or len(hypothesis.strip()) < 20:
                return []  # Fallback a Hybrid
            
            # PASO 2: Embeds hipótesis
            # ponytail: use embed_single instead of embed
            hypothesis_embedding = await self.embedder.embed_single(hypothesis)
            
            # PASO 3: Buscar en Qdrant con embedding de hipótesis
            agent_filter = build_agent_filter(agent_name)
            client_filter = build_client_filter(client_id)
            combined_filter = combine_filters(agent_filter, client_filter)
            
            results = self.qdrant.search(
                collection_name=self.collection,
                query_vector=hypothesis_embedding,
                query_filter=combined_filter,
                limit=top_k,
                with_payload=True
            )
            
            # ponytail: instantiate RetrievedChunk matching class definition
            return [
                RetrievedChunk(
                    chunk_id=str(r.id),
                    document_id=r.payload.get("document_id", ""),
                    text=r.payload.get("content", r.payload.get("text", "")),
                    score=r.score,
                    metadata=r.payload
                )
                for r in results
            ]
            
        except Exception as e:
            # Log el error pero no propagar — activar fallback silenciosamente
            logger.warning(f"HyDE retrieval failed for query '{query[:50]}': {e}")
            return []
    
    async def _generate_hypothesis(self, query: str) -> str:
        """
        Llama a Ollama con HYDE_PROMPT_TEMPLATE.
        Modelo: llama3.1:8b (rápido, suficiente para hipótesis cortas)
        Timeout: 5 segundos
        max_tokens: 200
        """
        prompt = self.HYDE_PROMPT_TEMPLATE.format(query=query)
        try:
            response = await asyncio.wait_for(
                self.ollama_client.generate(prompt=prompt, max_tokens=200),
                timeout=5.0
            )
            logger.debug(f"HyDE generated hypothesis: {response}")
            return response
        except asyncio.TimeoutError:
            logger.warning("HyDE generation timed out.")
            return ""
