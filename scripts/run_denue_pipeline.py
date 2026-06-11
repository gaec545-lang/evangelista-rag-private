import os
import sys
import datetime
import logging
from dotenv import load_dotenv

# Asegurar que el path alcance src
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.data_library.denue_extractor import DenueExtractor
from src.tools.database_connector import engine
from sqlalchemy import text

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def setup_db():
    if engine is None:
        logger.error("Database connection not configured. Skipping DB setup.")
        return
        
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS denue_pipeline_logs (
                id SERIAL PRIMARY KEY,
                execution_time TIMESTAMP,
                condition VARCHAR(255),
                total_records INT,
                size_counts JSONB,
                status VARCHAR(50)
            )
        """))

def log_execution(condition, total_records, size_counts, status="SUCCESS"):
    if engine is None:
        logger.error("Database connection not configured. Cannot log execution.")
        return
        
    import json
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO denue_pipeline_logs (execution_time, condition, total_records, size_counts, status)
            VALUES (:time, :cond, :rec, :counts, :stat)
        """), {
            "time": datetime.datetime.now(),
            "cond": condition,
            "rec": total_records,
            "counts": json.dumps(size_counts),
            "stat": status
        })
        logger.info("Logged execution to Azure SQL (PostgreSQL).")

def main():
    # Load env
    env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
    load_dotenv(env_path)
    
    setup_db()
    
    extractor = DenueExtractor(token_env_var='INEGI_TOKEN', env_path=env_path)
    
    # Zonas de ejemplo: CDMX centro (aprox)
    zones = [
        {"lat": "19.432608", "lon": "-99.133209"},
        {"lat": "19.427000", "lon": "-99.167600"}
    ]
    condition = "restaurantes"
    
    logger.info("Iniciando pipeline de extracción de DENUE...")
    
    try:
        results = extractor.extract_paginated(condition=condition, zones=zones, meters=500)
        logger.info(f"Pipeline finalizado. Registros totales: {results['total_records']}")
        log_execution(condition, results['total_records'], results['size_counts'], status="SUCCESS")
    except Exception as e:
        logger.error(f"Error en pipeline: {e}")
        log_execution(condition, 0, {}, status=f"FAILED: {str(e)[:200]}")

if __name__ == "__main__":
    main()
