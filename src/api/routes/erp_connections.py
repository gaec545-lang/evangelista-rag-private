"""ERP Connections router – Supabase removed. Placeholder implementation for alternative storage."""

from fastapi import APIRouter, HTTPException

router = APIRouter()

def _not_impl():
    # ponytail: raising HTTPException avoids unhandled 500 server crashes
    raise HTTPException(status_code=501, detail="Funcionalidad de conexiones ERP no implementada.")

@router.get("/api/v1/erp-connections")
async def list_connections():
    _not_impl()

@router.post("/api/v1/erp-connections/test-direct")
async def test_connection_direct():
    _not_impl()

@router.post("/api/v1/erp-connections/test/{source_id}")
async def test_stored_connection(source_id: str):
    _not_impl()

@router.delete("/api/v1/erp-connections/{connection_id}")
async def revoke_connection(connection_id: str):
    _not_impl()

