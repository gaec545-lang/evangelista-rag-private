from dataclasses import dataclass
from typing import Literal
from src.llm.ollama_client import OllamaClient
from src.config import settings

QueryType = Literal["FACTUAL", "PROCEDURAL", "METODOLOGICO", "CREATIVO"]
RetrieverType = Literal["HYBRID", "HYDE"]

@dataclass
class QueryClassification:
    query_type: QueryType
    retriever: RetrieverType
    confidence: float
    matched_keywords: list[str]

class QueryClassifier:
    
    async def classify(self, query: str) -> QueryClassification:
        """
        Delega la clasificación directamente al LLM (Ollama).
        """
        return await self._llm_classify(query)
    
    async def _llm_classify(self, query: str) -> QueryClassification:
        """
        Llama a Ollama con este prompt exacto.
        Esperar respuesta de 1 sola palabra.
        Si falla → default FACTUAL con confidence 0.5.
        """
        llm_to_retriever = {
            "FACTUAL": "HYBRID",
            "PROCEDURAL": "HYDE",
            "METODOLOGICO": "HYDE",
            "CREATIVO": "HYDE"
        }
        
        prompt = f"""Clasifica esta consulta en UNA sola palabra de estas opciones:
FACTUAL, PROCEDURAL, METODOLOGICO, CREATIVO.

Consulta: {query}

Responde solo con la palabra, sin explicación:"""

        try:
            client = OllamaClient(base_url=settings.OLLAMA_BASE_URL, model=settings.HYDE_MODEL)
            response = await client.generate(prompt)
            
            response_text = str(response).strip().upper()
            
            for qtype, retriever in llm_to_retriever.items():
                if qtype in response_text:
                    return QueryClassification(
                        query_type=qtype, # type: ignore
                        retriever=retriever, # type: ignore
                        confidence=0.8,
                        matched_keywords=[]
                    )
        except Exception:
            pass
            
        return QueryClassification(
            query_type="FACTUAL",
            retriever="HYBRID",
            confidence=0.5,
            matched_keywords=[]
        )
