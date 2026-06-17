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
        
    try:
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
    except Exception as e:
        logger.warning(f"No se pudo conectar a la base de datos para setup: {e}")


def log_execution(condition, total_records, size_counts, status="SUCCESS"):
    if engine is None:
        logger.error("Database connection not configured. Cannot log execution.")
        return
        
    import json
    try:
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
    except Exception as e:
        logger.warning(f"No se pudo registrar en base de datos: {e}")

def generate_markdown(total_records, size_counts):
    vault_dir = r"e:\Evangelista & Co\Evangelista Intelligence Platform\Evangelista-Obsidian\evangelista-vault"
    output_dir = os.path.join(vault_dir, "benchmarks", "denue")
    os.makedirs(output_dir, exist_ok=True)
    
    output_path = os.path.join(output_dir, "DAT-DENUE-restaurantes.md")
    
    date_str = datetime.datetime.now().strftime("%Y-%m-%d")
    
    md_content = f"""---
id: DAT-DENUE-RESTAURANTES-{date_str}
tipo: benchmark_sectorial
subtipo: censo_economico
nivel_geografico: Puebla_centro
fecha_extraccion: {date_str}
---

## Resumen de Extraccion DENUE

**Condicion:** Restaurantes
**Registros Totales:** {total_records}

## Distribucion por Tamano de Establecimiento

| Tamano de Establecimiento | Numero de Establecimientos |
|---------------------------|----------------------------|
"""
    for size, count in size_counts.items():
        md_content += f"| {size} | {count} |\n"
        
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(md_content)
    
    logger.info(f"Archivo Markdown generado en: {output_path}")

def main():
    # Load env
    env_path = r"e:\Evangelista & Co\Evangelista Intelligence Platform\Evangelista-Obsidian\evangelista-vault\.env"
    load_dotenv(env_path)
    
    setup_db()
    
    extractor = DenueExtractor(token_env_var='INEGI_TOKEN', env_path=env_path)
    
    # Zonas de ejemplo: Puebla (centro aprox)
    zones = [
        {"lat": "19.0414", "lon": "-98.2063"},
        {"lat": "19.0500", "lon": "-98.2000"}
    ]
    condition = "restaurantes"
    
    logger.info("Iniciando pipeline de extracción de DENUE...")
    
    try:
        results = extractor.extract_paginated(condition=condition, zones=zones, meters=500)
        logger.info(f"Pipeline finalizado. Registros totales: {results['total_records']}")
        log_execution(condition, results['total_records'], results['size_counts'], status="SUCCESS")
        
        generate_markdown(results['total_records'], results['size_counts'])
    except Exception as e:
        logger.error(f"Error en pipeline: {e}")
        log_execution(condition, 0, {}, status=f"FAILED: {str(e)[:200]}")

if __name__ == "__main__":
    main()
