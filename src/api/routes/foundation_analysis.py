import os
import tempfile
import asyncio
import shutil
from pathlib import Path
from uuid import UUID

import pandas as pd
import structlog
from fastapi import APIRouter, File, HTTPException, UploadFile, Form, BackgroundTasks
from fastapi.responses import JSONResponse
from supabase import create_client

from src.analysis.data_profiler import profile_csv, profile_dataframe
from src.config import settings

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/foundation", tags=["Foundation Analysis"])


def _get_supabase():
    url = getattr(settings, "SUPABASE_URL", os.environ.get("SUPABASE_URL", ""))
    key = getattr(settings, "SUPABASE_SERVICE_KEY", os.environ.get("SUPABASE_SERVICE_KEY", ""))
    if not url or not key:
        key = getattr(settings, "SUPABASE_SERVICE_ROLE_KEY", os.environ.get("SUPABASE_SERVICE_ROLE_KEY", ""))
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY required")
    return create_client(url, key)


async def _save_ingestion_record(sb, engagement_id: str, source_type: str, filename: str, status: str = "completed", result: dict = None):
    """Insert the ingestion event in data_ingestions table."""
    payload = {
        "engagement_id": engagement_id,
        "source_type": source_type,
        "raw_filename": filename,
        "status": status,
    }
    if result:
        payload.update({
            "row_count": result.get("row_count"),
            "column_count": result.get("column_count"),
            "detected_params": {
                "registros_estimados": result.get("registros_estimados"),
                "fuentes_datos": result.get("fuentes_datos"),
                "nodo_critico": result.get("nodo_critico"),
                "sucursales": result.get("sucursales"),
                "erp_type": result.get("erp_type"),
                "confidence_scores": result.get("confidence_scores", {}),
            },
        })
    
    try:
        res = sb.table("data_ingestions").insert(payload).execute()
        return res.data[0]["id"] if res.data else None
    except Exception as e:
        logger.warning("failed_to_save_ingestion", error=str(e))
        return None


async def process_ingestion_task(engagement_id: str, file_path: Path, filename: str, source_type: str, ingestion_id: str):
    """Background task to profile file and update DB."""
    sb = _get_supabase()
    try:
        # Profile in threadpool to avoid blocking
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, profile_csv, file_path)
        
        # Update record
        sb.table("data_ingestions").update({
            "status": "completed",
            "row_count": result.get("row_count"),
            "column_count": result.get("column_count"),
            "detected_params": {
                "registros_estimados": result.get("registros_estimados"),
                "fuentes_datos": result.get("fuentes_datos"),
                "nodo_critico": result.get("nodo_critico"),
                "sucursales": result.get("sucursales"),
                "erp_type": result.get("erp_type"),
                "confidence_scores": result.get("confidence_scores", {}),
            },
        }).eq("id", ingestion_id).execute()
        
        logger.info("ingestion_completed", id=ingestion_id, rows=result.get("row_count"))
    except Exception as e:
        logger.error("ingestion_failed", id=ingestion_id, error=str(e))
        try:
            sb.table("data_ingestions").update({
                "status": "failed",
                "error_message": str(e)
            }).eq("id", ingestion_id).execute()
        except:
            pass
    finally:
        if file_path.exists():
            os.unlink(file_path)


async def _save_ingestion(sb, engagement_id: str, source_type: str, filename: str, result: dict):
    """Legacy helper for sync ingestion (ERP)."""
    try:
        sb.table("data_ingestions").insert({
            "engagement_id": engagement_id,
            "source_type": source_type,
            "raw_filename": filename,
            "status": "completed",
            "row_count": result.get("row_count"),
            "column_count": result.get("column_count"),
            "detected_params": {
                "registros_estimados": result.get("registros_estimados"),
                "fuentes_datos": result.get("fuentes_datos"),
                "nodo_critico": result.get("nodo_critico"),
                "sucursales": result.get("sucursales"),
                "erp_type": result.get("erp_type"),
                "confidence_scores": result.get("confidence_scores", {}),
            },
        }).execute()
    except Exception as e:
        logger.warning("failed_to_save_ingestion", error=str(e))


@router.post("/{client_id}/analyze-upload")
async def analyze_upload(
    client_id: str, 
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...), 
    engagement_id: str = Form(None)
):
    """Upload a CSV or Excel file and auto-detect Foundation scoping parameters asynchronously.

    Returns a job ID immediately while processing in background.
    """
    allowed = {".csv", ".xlsx", ".xls", ".tsv"}
    ext = Path(file.filename or "").suffix.lower()
    if ext not in allowed:
        raise HTTPException(400, f"Formato no soportado: {ext}. Use CSV, TSV o Excel.")

    # Create ingestion record as 'processing'
    sb = _get_supabase()
    ingestion_id = await _save_ingestion_record(
        sb, engagement_id, ext.lstrip("."), file.filename, status="processing"
    )

    # Save to temp file using streaming to optimize memory
    fd, tmp_path = tempfile.mkstemp(suffix=ext)
    try:
        with os.fdopen(fd, 'wb') as tmp:
            shutil.copyfileobj(file.file, tmp)
    except Exception as e:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise HTTPException(500, f"Error al guardar archivo: {str(e)}")

    # Add to background tasks
    background_tasks.add_task(
        process_ingestion_task, 
        engagement_id, Path(tmp_path), file.filename, ext.lstrip("."), ingestion_id
    )

    return {
        "status": "processing",
        "ingestion_id": ingestion_id,
        "message": "Análisis iniciado en segundo plano."
    }


@router.get("/ingestion/{ingestion_id}/status")
async def get_ingestion_status(ingestion_id: str):
    """Check the status of a background ingestion task."""
    sb = _get_supabase()
    res = sb.table("data_ingestions").select("*").eq("id", ingestion_id).execute()
    if not res.data:
        raise HTTPException(404, "Ingesta no encontrada")
    return res.data[0]


@router.post("/{client_id}/analyze-erp")
async def analyze_erp(client_id: str, connection_id: str | None = None, engagement_id: str = Form(None)):
    """Profile the client's ERP database via existing ERP connection.

    Uses the encrypted DB connection to inspect table structure and row counts.
    """
    try:
        from src.tools.database_connector import get_ephemeral_connection

        conn = get_ephemeral_connection(client_id, connection_id)

        try:
            import psycopg2
            cursor = conn.cursor()

            # Get table list and row counts
            cursor.execute("""
                SELECT table_schema, table_name,
                       (xpath('/row/cnt/text()', xml_count))[1]::text::int as row_count
                FROM (
                    SELECT table_schema, table_name,
                           query_to_xml(format('select count(*) as cnt from %I.%I', table_schema, table_name),
                                        false, true, '') as xml_count
                    FROM information_schema.tables
                    WHERE table_schema NOT IN ('pg_catalog', 'information_schema', 'vault', 'storage', 'graphql', 'cron')
                    ORDER BY table_schema, table_name
                ) t
                LIMIT 200
            """)
            tables = cursor.fetchall()

            if not tables:
                # Fallback: simpler count query
                cursor.execute("""
                    SELECT schemaname, relname, n_live_tup
                    FROM pg_stat_user_tables
                    WHERE schemaname NOT IN ('pg_catalog', 'information_schema', 'vault')
                    ORDER BY n_live_tup DESC
                    LIMIT 200
                """)
                tables = cursor.fetchall()

            total_rows = sum(t[2] for t in tables if t[2])
            table_count = len(tables)

            # Sample first large table for column analysis
            largest_table = max(tables, key=lambda t: t[2] or 0)
            schema_name, table_name = largest_table[0], largest_table[1]

            from psycopg2 import sql
            query = sql.SQL("""
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_schema = %s AND table_name = %s
                ORDER BY ordinal_position
                LIMIT 100
            """)
            cursor.execute(query, (schema_name, table_name))
            columns = cursor.fetchall()

            col_names = [c[0] for c in columns]

            # Build a minimal dataframe for detection
            df = pd.DataFrame(columns=col_names)
            profile = profile_dataframe(df, f"erp://{schema_name}.{table_name}")

            profile["row_count"] = total_rows
            profile["registros_estimados"] = total_rows
            profile["fuentes_datos"] = max(profile["fuentes_datos"], table_count)
            profile["column_count"] = len(columns)
            profile["table_count"] = table_count
            profile["largest_table"] = f"{schema_name}.{table_name}"

            if engagement_id:
                sb = _get_supabase()
                await _save_ingestion(sb, engagement_id, "erp", f"{schema_name}.{table_name}", profile)

            logger.info("erp_analyzed", client_id=client_id, tables=table_count, total_rows=total_rows)
            return JSONResponse(content=profile)

        finally:
            conn.close()

    except ImportError:
        raise HTTPException(500, "psycopg2 no instalado. pip install psycopg2-binary")
    except KeyError as e:
        raise HTTPException(404, f"Conexion ERP no encontrada: {e}")
    except Exception as e:
        logger.error("erp_analysis_failed", client_id=client_id, error=str(e))
        raise HTTPException(500, f"Error analizando ERP: {str(e)}")
