"""Configuración central del pipeline RAG de Evangelista & Co."""
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Configuración cargada desde variables de entorno o archivo .env."""

    # Vault
    # En producción (Render), el conocimiento está dentro del repo como submódulo 'vault'
    VAULT_PATH: str = "./vault"

    # Qdrant
    # "local" usa archivos en disco. "server" usa host:port (recomendado para producción con persistencia).
    QDRANT_MODE: str = "local"
    QDRANT_LOCAL_PATH: str = "./qdrant_storage"
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333
    QDRANT_COLLECTION: str = "evangelista_knowledge"

    # LLM Provider: "groq" (Recomendado para velocidad en producción)
    LLM_PROVIDER: str = "groq"
    LLM_MODEL: str = "groq-llama-70b"

    # Groq (dev/prod)
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.3-70b-versatile"

    # Ollama (solo para desarrollo local)
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "qwen2.5:32b"
    OLLAMA_EMBED_MODEL: str = "nomic-embed-text"

    # Anthropic (fallback)
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-sonnet-4-5-20251022"

    # Embeddings
    # Usamos "fastembed" como default porque es local, rápido y no necesita servidor externo (Ollama).
    EMBED_PROVIDER: str = "fastembed"
    EMBED_MODEL: str = "BAAI/bge-small-en-v1.5"
    EMBED_DIMENSIONS: int = 384

    # Chunking
    CHUNK_MIN_LENGTH: int = 100
    CHUNK_MAX_LENGTH: int = 2000
    CHUNK_OVERLAP: int = 200

    # Retrieval
    RETRIEVAL_TOP_K: int = 10
    RETRIEVAL_FINAL_K: int = 5
    RERANKER_ENABLED: bool = False

    # Supabase (para team management desde backend)
    SUPABASE_URL: str = ""
    SUPABASE_SERVICE_KEY: str = ""

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",  # Allow extra env vars without failing
    }


@lru_cache
def get_settings() -> Settings:
    """Retorna la instancia singleton de Settings."""
    return Settings()


settings = get_settings()
