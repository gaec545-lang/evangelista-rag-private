"""Foundation Analysis router – Supabase removed. Placeholder implementation for Azure or other storage."""

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api/v1/foundation", tags=["Foundation Analysis"])

def _not_impl():
    # ponytail: raising HTTPException avoids unhandled 500 server crashes
    raise HTTPException(status_code=501, detail="Funcionalidad de análisis Foundation no implementada.")

@router.post("/{client_id}/analyze-upload")
async def analyze_upload(client_id: str, background_tasks: BackgroundTasks, file: UploadFile = File(...), engagement_id: str = Form(None)):
    _not_impl()

@router.get("/ingestion/{ingestion_id}/status")
async def get_ingestion_status(ingestion_id: str):
    _not_impl()

@router.post("/{client_id}/analyze-erp")
async def analyze_erp(client_id: str, connection_id: str | None = None, engagement_id: str = Form(None)):
    _not_impl()
