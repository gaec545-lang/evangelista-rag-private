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

CLASSIFICATION_MAP = {
    "FACTUAL": {
        "retriever": "HYBRID",
        "keywords": [
            "qué es", "define", "cuánto", "cuál es", "quién",
            "cuándo", "dónde", "qué significa", "explica", "descripción"
        ],
        "weight": 1.0
    },
    "PROCEDURAL": {
        "retriever": "HYDE",
        "keywords": [
            "cómo", "pasos", "estructur", "armar", "crear", "construir",
            "implementar", "ejecutar", "proceso de", "procedimiento",
            "cómo hago", "cómo puedo", "guíame"
        ],
        "weight": 1.0
    },
    "METODOLOGICO": {
        "retriever": "HYDE",
        "keywords": [
            "framework", "mece", "dmaic", "sipoc", "issue tree",
            "aplicar", "metodología", "análisis", "diagnóstico",
            "minto", "coi", "cost of inaction", "hipótesis", "alcoa"
        ],
        "weight": 1.2
    },
    "CREATIVO": {
        "retriever": "HYDE",
        "keywords": [
            "propón", "sugiere", "diseña", "recomienda", "alternativas",
            "ideas para", "opciones de", "qué estrategia", "cómo mejorar"
        ],
        "weight": 0.9
    }
}

class QueryClassifier:
    
    CONFIDENCE_THRESHOLD = settings.RAG_CLASSIFIER_CONFIDENCE_THRESHOLD
    
    async def classify(self, query: str) -> QueryClassification:
        """
        1. Normaliza query a minúsculas
        2. Para cada tipo en CLASSIFICATION_MAP, cuenta keywords que aparecen en la query
        3. Calcula score = (keywords_matched / total_keywords_del_tipo) * weight
        4. Selecciona tipo con mayor score
        5. confidence = score / max_possible_score (normalizado a [0,1])
        6. Si confidence < CONFIDENCE_THRESHOLD → fallback a Ollama
        """
        query_lower = query.lower()
        best_type = None
        best_score = 0.0
        best_keywords = []
        
        for qtype, config in CLASSIFICATION_MAP.items():
            matched = [kw for kw in config["keywords"] if kw in query_lower]
            if matched:
                score = (len(matched) / len(config["keywords"])) * config["weight"]
                if score > best_score:
                    best_score = score
                    best_type = qtype
                    best_keywords = matched
        
        confidence = min(best_score * 3.0, 1.0)
        
        if best_type is None or confidence < self.CONFIDENCE_THRESHOLD:
            return await self._llm_classify(query)
        
        # Mapear types a su retriever correspondiente y castear a Literal para type hint si fuera estricto
        retriever = CLASSIFICATION_MAP[best_type]["retriever"]
        
        return QueryClassification(
            query_type=best_type,  # type: ignore
            retriever=retriever,   # type: ignore
            confidence=confidence,
            matched_keywords=best_keywords
        )
    
    async def _llm_classify(self, query: str) -> QueryClassification:
        """
        Fallback: llama a Ollama con este prompt exacto.
        Esperar respuesta de 1 sola palabra.
        Timeout: 3 segundos. Si falla → default FACTUAL con confidence 0.5.
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
            # Assuming generate takes prompt and we can set timeout if supported, otherwise just rely on defaults
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
