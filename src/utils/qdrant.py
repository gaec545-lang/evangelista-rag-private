"""Utilidades para la gestión de la conexión a Qdrant."""
from qdrant_client import QdrantClient
from src.config import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)

_shared_client: QdrantClient | None = None

def get_qdrant_client() -> QdrantClient:
    """Retorna un cliente Qdrant compartido (Singleton) para evitar bloqueos en modo local."""
    global _shared_client
    if _shared_client is None:
        try:
            if settings.QDRANT_MODE == "local":
                logger.info("inicializando_qdrant_local", path=settings.QDRANT_LOCAL_PATH)
                _shared_client = QdrantClient(path=settings.QDRANT_LOCAL_PATH)
            else:
                logger.info("inicializando_qdrant_server", host=settings.QDRANT_HOST, port=settings.QDRANT_PORT)
                _shared_client = QdrantClient(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT)
        except Exception as e:
            logger.error("error_inicializando_qdrant", error=str(e))
            raise
    return _shared_client

def close_qdrant_client():
    """Cierra la conexión compartida si existe."""
    global _shared_client
    if _shared_client:
        # En modo local en Windows, cerrar es vital para liberar el lock de portalocker
        try:
            _shared_client.close()
            logger.info("conexion_qdrant_cerrada")
        except Exception:
            pass
        _shared_client = None
