import os
import pyodbc
from datetime import datetime

def log_run(pipeline_name: str, status: str, records_processed: int, error_message: str = None):
    """
    Registra la ejecución del pipeline en Azure SQL.
    Asegurarse de que DATABASE_URL o AZURE_SQL_CONNECTION_STRING esté en el entorno.
    """
    conn_str = os.environ.get("AZURE_SQL_CONNECTION_STRING") or os.environ.get("DATABASE_URL")
    if not conn_str:
        print(f"[{datetime.now()}] MOCK Azure SQL LOG: Pipeline '{pipeline_name}' finished. Status: {status}. Records: {records_processed}. Error: {error_message}")
        return
        
    conn = None
    try:
        if "pyodbc" not in conn_str and "Server=" in conn_str:
            conn = pyodbc.connect(conn_str)
        else:
            # Simple mockup connection for the sake of the environment if we can't parse it
            conn = pyodbc.connect(conn_str)
            
        cursor = conn.cursor()
        
        query = """
        INSERT INTO data_library_runs (source, status, records_extracted, error_message, run_date, created_at)
        VALUES (?, ?, ?, ?, SYSDATETIMEOFFSET(), SYSDATETIMEOFFSET())
        """
        cursor.execute(query, pipeline_name, status, records_processed, error_message)
        conn.commit()
    except Exception as e:
        print(f"Error logging to Azure SQL: {e}")
    finally:
        if conn:
            # ponytail: always close connection in finally block to prevent connection leaks
            try:
                conn.close()
            except Exception:
                pass
