"""Reranker opcional para mejora de resultados (requiere GPU)."""
from src.core.models import SearchResult
from src.utils.logger import get_logger

logger = get_logger(__name__)


class Reranker:
    """
    Reranker basado en bge-reranker-v2-m3.
    Solo se activa si RERANKER_ENABLED=true y hay GPU disponible.
    En CPU puro, devuelve los resultados sin modificar.
    """

    def __init__(self, model_name: str = "BAAI/bge-reranker-v2-m3", enabled: bool = False) -> None:
        self.enabled = enabled
        self.model = None
        if enabled:
            try:
                from sentence_transformers import CrossEncoder
                self.model = CrossEncoder(model_name)
                logger.info("reranker_cargado", model=model_name)
            except ImportError:
                logger.warning("sentence_transformers_no_disponible", fallback="sin_reranking")
                self.enabled = False

    def rerank(self, query: str, results: list[SearchResult], top_k: int) -> list[SearchResult]:
        """
        Reordena los resultados por relevancia con el modelo de reranking.
        Si el reranker no está habilitado, retorna los primeros top_k sin modificar.
        """
        if not self.enabled or self.model is None:
            return results[:top_k]

        pairs = [[query, r.content] for r in results]
        scores = self.model.predict(pairs)

        for result, score in zip(results, scores):
            result.score = float(score)

        reranked = sorted(results, key=lambda r: r.score, reverse=True)
        logger.info("resultados_rerankeados", total_input=len(results), top_k=top_k)
        return reranked[:top_k]
