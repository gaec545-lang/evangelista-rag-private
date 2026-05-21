import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Configuración de conexión para Azure SQL (PyODBC)
# Formato esperado: mssql+pyodbc://<username>:<password>@<server>.database.windows.net/<db>?driver=ODBC+Driver+17+for+SQL+Server
DATABASE_URL = os.getenv("AZURE_SQL_CONNECTION_STRING", "sqlite:///./local_dev.db")

try:
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    logger.info("Database engine created successfully.")
except Exception as e:
    logger.error(f"Failed to create database engine: {e}")
    engine = None
    SessionLocal = None

Base = declarative_base()

def get_db():
    """Dependency para inyectar la sesión de base de datos en las rutas de FastAPI."""
    if SessionLocal is None:
        raise RuntimeError("Database connection not configured.")
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
