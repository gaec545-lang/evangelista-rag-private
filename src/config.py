"""Configuración central del pipeline RAG de Evangelista & Co."""
import os
import logging
from pydantic_settings import BaseSettings
from functools import lru_cache

logger = logging.getLogger(__name__)

class Settings(BaseSettings):
    """Configuración cargada desde variables de entorno o archivo .env."""

    AZURE_KEY_VAULT_URL: str = os.getenv("AZURE_KEY_VAULT_URL", "")

    # Vault
    VAULT_PATH: str = "./vault"

    # Qdrant
    QDRANT_MODE: str = "local"
    QDRANT_LOCAL_PATH: str = "./qdrant_storage"
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333
    QDRANT_COLLECTION: str = "evangelista_knowledge"

    # LLM Provider
    LLM_PROVIDER: str = "groq"
    LLM_MODEL: str = "groq-llama-70b"

    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.3-70b-versatile"

    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "qwen2.5:32b"
    OLLAMA_EMBED_MODEL: str = "nomic-embed-text"

    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-sonnet-4-5-20251022"

    EMBED_PROVIDER: str = "fastembed"
    EMBED_MODEL: str = "BAAI/bge-small-en-v1.5"
    EMBED_DIMENSIONS: int = 384

    CHUNK_MIN_LENGTH: int = 100
    CHUNK_MAX_LENGTH: int = 2000
    CHUNK_OVERLAP: int = 200

    RETRIEVAL_TOP_K: int = 10
    RETRIEVAL_FINAL_K: int = 5
    RERANKER_ENABLED: bool = False

    RAG_RELEVANCE_THRESHOLD: float = 0.65
    RAG_TOP_K: int = 8
    RAG_HYDE_TIMEOUT_SECONDS: float = 5.0
    RAG_BM25_TOP_K_INTERMEDIATE: int = 20
    RAG_CLASSIFIER_CONFIDENCE_THRESHOLD: float = 0.70
    HYDE_MODEL: str = "llama3.1:8b"

    # Entra ID for Auth
    ENTRA_ID_TENANT_ID: str = ""
    ENTRA_ID_CLIENT_ID: str = ""
    
    # DB
    DATABASE_URL: str = ""
    ASYNC_DATABASE_URL: str = ""

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }

    def load_secrets(self):
        if not self.AZURE_KEY_VAULT_URL:
            return
        
        try:
            from azure.identity import DefaultAzureCredential
            from azure.keyvault.secrets import SecretClient
            from azure.core.exceptions import ResourceNotFoundError
            
            credential = DefaultAzureCredential()
            client = SecretClient(vault_url=self.AZURE_KEY_VAULT_URL, credential=credential)
            
            secret_mapping = {
                "DATABASE_URL": "pg-connection-string",
                "ASYNC_DATABASE_URL": "pg-async-connection-string",
                "GROQ_API_KEY": "groq-api-key",
                "ANTHROPIC_API_KEY": "anthropic-api-key"
            }
            
            for attr, secret_name in secret_mapping.items():
                try:
                    secret = client.get_secret(secret_name)
                    if secret.value:
                        setattr(self, attr, secret.value)
                except ResourceNotFoundError:
                    pass
        except ImportError:
            logger.warning("azure-identity or azure-keyvault-secrets not installed.")
        except Exception as e:
            logger.warning(f"Error reading from Azure Key Vault: {e}")

@lru_cache
def get_settings() -> Settings:
    """Retorna la instancia singleton de Settings."""
    s = Settings()
    s.load_secrets()
    return s

settings = get_settings()
