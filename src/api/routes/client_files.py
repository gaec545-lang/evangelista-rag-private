"""Client Files routes – Supabase removed. Placeholder implementation for Azure storage or other solution."""

from fastapi import APIRouter, UploadFile, File, HTTPException
from src.utils.logger import get_logger
import uuid

router = APIRouter(prefix="/api/v1/clients", tags=["Client Files"])

logger = get_logger(__name__)

def _not_impl():
    raise NotImplementedError("File storage functionality removed – implement Azure Blob Storage or equivalent.")

@router.get("/{client_id}/files")
async def list_files(client_id: str):
    _not_impl()

@router.post("/{client_id}/files")
async def upload_file(client_id: str, file: UploadFile = File(...)):
    _not_impl()

@router.delete("/{client_id}/files/{filename}")
async def delete_file(client_id: str, filename: str):
    _not_impl()
