import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from src.utils.logger import get_logger
from src.config import settings

logger = get_logger(__name__)

# Configuración de conexión para PostgreSQL
# Formato esperado: postgresql://<username>:<password>@<host>:<port>/<db>
# Para async: postgresql+asyncpg://<username>:<password>@<host>:<port>/<db>
DATABASE_URL = settings.DATABASE_URL or os.getenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/evangelista_db")
ASYNC_DATABASE_URL = settings.ASYNC_DATABASE_URL or os.getenv("ASYNC_DATABASE_URL", "postgresql+asyncpg://user:pass@localhost:5432/evangelista_db")

try:
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        pool_recycle=1800
    )
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

def get_ephemeral_connection():
    """Mock connection function for compatibility."""
    if engine is None:
        raise RuntimeError("Database connection not configured.")
    return engine.connect()

