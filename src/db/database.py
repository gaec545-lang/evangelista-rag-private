import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base

from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

from src.config import settings

DATABASE_URL = settings.ASYNC_DATABASE_URL or settings.DATABASE_URL or "postgresql+asyncpg://user:password@localhost/dbname"
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

connect_args = {}
if "asyncpg" in DATABASE_URL:
    parsed_url = urlparse(DATABASE_URL)
    query_params = parse_qs(parsed_url.query)
    if "sslmode" in query_params:
        sslmode = query_params.pop("sslmode")[0]
        if sslmode != "disable":
            connect_args["ssl"] = True
        new_query = urlencode(query_params, doseq=True)
        parsed_url = parsed_url._replace(query=new_query)
        DATABASE_URL = urlunparse(parsed_url)

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    connect_args=connect_args,
    pool_pre_ping=True,
    pool_recycle=1800
)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
Base = declarative_base()

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
