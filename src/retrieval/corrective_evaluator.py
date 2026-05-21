from dataclasses import dataclass
from typing import List, Literal
from .hybrid_retriever import RetrievedChunk
from src.config import settings

@dataclass
class EvaluationResult:
    status: Literal["OK", "INSUFFICIENT_CONTEXT"]
    approved_chunks: List[RetrievedChunk]
    avg_score: float
    rejected_count: int

class CorrectivenessEvaluator:
    
    RELEVANCE_THRESHOLD = settings.RAG_RELEVANCE_THRESHOLD
    
    def evaluate(
        self, 
        chunks: List[RetrievedChunk], 
        query: str
    ) -> EvaluationResult:
        """
        Calcula weighted_score por chunk:
            weighted_score = (0.6 * semantic_score) + (0.4 * bm25_score)
        
        Filtra chunks donde weighted_score < RELEVANCE_THRESHOLD.
        
        Si approved_chunks está vacío → status = "INSUFFICIENT_CONTEXT"
        Si hay al menos 1 chunk aprobado → status = "OK"
        """
        
        approved = []
        rejected_count = 0
        
        for chunk in chunks:
            weighted_score = (0.6 * chunk.semantic_score) + (0.4 * chunk.bm25_score)
            
            if weighted_score >= self.RELEVANCE_THRESHOLD:
                # Actualizar el score del chunk con el weighted score
                chunk.score = weighted_score
                approved.append(chunk)
            else:
                rejected_count += 1
        
        if not approved:
            return EvaluationResult(
                status="INSUFFICIENT_CONTEXT",
                approved_chunks=[],
                avg_score=0.0,
                rejected_count=rejected_count
            )
        
        avg = sum(c.score for c in approved) / len(approved)
        
        return EvaluationResult(
            status="OK",
            approved_chunks=approved,
            avg_score=avg,
            rejected_count=rejected_count
        )
