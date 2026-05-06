"""ERP Connections router — Evangelista Intelligence Platform."""
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from src.utils.logger import get_logger
from src.tools.database_connector import _open_readonly_connection, get_supabase_client
import time

logger = get_logger(__name__)

router = APIRouter()

# ─── Schemas ───

class ErpConnectionCreate(BaseModel):
    project_id: str
    client_id: str
    name: str
    source_type: str
    connection_config: dict
    authorized_tables: list[str] = []
    notes: Optional[str] = None

class TestRequest(BaseModel):
    source_type: str
    connection_config: dict

class TestResult(BaseModel):
    success: bool
    message: str
    latency_ms: Optional[float] = None


# ─── Endpoints ───

@router.get("/api/v1/erp-connections", tags=["ERP Connections"])
async def list_connections(project_id: Optional[str] = None):
    """List all ERP connections from Supabase."""
    sb = get_supabase_client()
    query = sb.table("data_sources").select("*")
    if project_id:
        query = query.eq("project_id", project_id)
    
    response = query.execute()
    return response.data


@router.post("/api/v1/erp-connections/test-direct", response_model=TestResult, tags=["ERP Connections"])
async def test_connection_direct(data: TestRequest):
    """
    Test an ERP connection using provided config.
    DOES NOT persist anything, just tests the connectivity.
    """
    start = time.time()
    config = data.connection_config
    stype = data.source_type

    try:
        # Host/Port check for SQL-based sources
        if stype in ['sql_server', 'mysql', 'postgresql', 'oracle', 'sap_b1', 'contpaqi', 'aspel']:
            conn = _open_readonly_connection(
                db_type=stype,
                host=config.get('host', ''),
                port=int(config.get('port', 0)),
                database_name=config.get('database', ''),
                username=config.get('username', ''),
                password=config.get('password', ''),
            )
            # If we reach here, connection was successful
            if hasattr(conn, 'close'):
                conn.close()
            
            latency = (time.time() - start) * 1000
            return TestResult(
                success=True,
                message="Conexión exitosa — Acceso Read-Only verificado",
                latency_ms=round(latency, 1)
            )

        elif stype == 'api_rest':
            import httpx
            async with httpx.AsyncClient() as client:
                res = await client.get(config.get('base_url', ''), timeout=5.0)
                latency = (time.time() - start) * 1000
                return TestResult(
                    success=res.status_code < 400,
                    message=f"API respondió con status {res.status_code}",
                    latency_ms=round(latency, 1)
                )

        elif stype in ['excel', 'csv']:
            import os
            path = config.get('path', '')
            if os.path.exists(path):
                latency = (time.time() - start) * 1000
                return TestResult(
                    success=True,
                    message="Ruta de archivo accesible",
                    latency_ms=round(latency, 1)
                )
            else:
                return TestResult(success=False, message="La ruta especificada no existe o no es accesible por el backend")

        return TestResult(success=False, message=f"Tipo de fuente '{stype}' no soportado para test automático")

    except Exception as e:
        logger.error("connection_test_failed", error=str(e), source_type=stype)
        return TestResult(
            success=False,
            message=f"Error de conexión: {str(e)}",
            latency_ms=round((time.time() - start) * 1000, 1)
        )


@router.post("/api/v1/erp-connections/test/{source_id}", response_model=TestResult, tags=["ERP Connections"])
async def test_stored_connection(source_id: str):
    """Test a connection already stored in Supabase."""
    sb = get_supabase_client()
    res = sb.table("data_sources").select("*").eq("id", source_id).single().execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Fuente de datos no encontrada")
    
    source = res.data
    return await test_connection_direct(TestRequest(
        source_type=source['source_type'],
        connection_config=source['connection_config']
    ))


@router.delete("/api/v1/erp-connections/{connection_id}", tags=["ERP Connections"])
async def revoke_connection(connection_id: str):
    """Delete a connection from Supabase."""
    sb = get_supabase_client()
    res = sb.table("data_sources").delete().eq("id", connection_id).execute()
    return {"message": "Connection revoked", "id": connection_id}
