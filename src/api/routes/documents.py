from fastapi import APIRouter
from src.document_engine.factory import router as document_engine_router

router = APIRouter()
# Includimos el router del motor de documentos
router.include_router(document_engine_router, prefix="/documents")

# Mantenemos compatibilidad con rutas antiguas si es necesario
# pero delegaremos todo a /api/v1/documents/generate a través de server.py
