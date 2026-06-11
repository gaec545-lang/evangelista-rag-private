import os
import pyodbc
from datetime import datetime

def log_run(pipeline_name: str, status: str, records_processed: int, error_message: str = None):
    """
    Registra la ejecución del pipeline en Azure SQL.
    Asegurarse de que AZURE_SQL_CONNECTION_STRING esté en el entorno.
    """
    conn_str = os.environ.get("AZURE_SQL_CONNECTION_STRING")
    if not conn_str:
        print(f"[{datetime.now()}] MOCK Azure SQL LOG: Pipeline '{pipeline_name}' finished. Status: {status}. Records: {records_processed}. Error: {error_message}")
        return
        
    try:
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()
        
        # Asume la existencia de la tabla pipeline_logs
        query = """
        INSERT INTO pipeline_logs (pipeline_name, status, records_processed, error_message, execution_time)
        VALUES (?, ?, ?, ?, GETDATE())
        """
        cursor.execute(query, pipeline_name, status, records_processed, error_message)
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error logging to Azure SQL: {e}")
