"""Rutas para gestión de archivos por cliente (upload, list, delete)."""
from fastapi import APIRouter, UploadFile, File, HTTPException
from supabase import create_client
from src.config import settings
import uuid

router = APIRouter(prefix="/api/v1/clients", tags=["Client Files"])

supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)
BUCKET = "client-files"


@router.get("/{client_id}/files")
async def list_files(client_id: str):
    """Lista archivos del cliente en Supabase Storage."""
    try:
        result = supabase.storage.from_(BUCKET).list(path=client_id)
        files = [
            {"name": f["name"], "size": f.get("metadata", {}).get("size", 0), "uploaded_at": f.get("created_at", "")}
            for f in (result or [])
            if f.get("name") and not f["name"].startswith(".")
        ]
        return {"files": files}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{client_id}/files")
async def upload_file(client_id: str, file: UploadFile = File(...)):
    """Sube un archivo al bucket del cliente."""
    allowed = {".csv", ".tsv", ".xlsx", ".xls", ".pdf"}
    ext = "." + (file.filename or "").rsplit(".", 1)[-1].lower() if "." in (file.filename or "") else ""
    if ext not in allowed:
        raise HTTPException(status_code=400, detail=f"Tipo de archivo no permitido: {ext}")

    content = await file.read()
    if len(content) > 50 * 1024 * 1024:  # 50 MB limit
        raise HTTPException(status_code=400, detail="Archivo demasiado grande (máx 50 MB)")

    path = f"{client_id}/{file.filename}"
    try:
        supabase.storage.from_(BUCKET).upload(path, content, {"content-type": file.content_type or "application/octet-stream"})
        return {"status": "ok", "path": path, "name": file.filename, "size": len(content)}
    except Exception as e:
        if "Duplicate" in str(e) or "already exists" in str(e):
            # Overwrite
            supabase.storage.from_(BUCKET).update(path, content, {"content-type": file.content_type or "application/octet-stream"})
            return {"status": "ok", "path": path, "name": file.filename, "size": len(content)}
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{client_id}/files/{filename}")
async def delete_file(client_id: str, filename: str):
    """Elimina un archivo del bucket del cliente."""
    path = f"{client_id}/{filename}"
    try:
        supabase.storage.from_(BUCKET).remove([path])
        return {"status": "deleted", "path": path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
