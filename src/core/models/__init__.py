"""Modelos base de datos y estructuras Pydantic compartidas."""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date
import uuid


class VaultDocument(BaseModel):
    """Documento .md parseado del vault con su frontmatter YAML completo."""

    # Campos del frontmatter YAML
    id: str
    title: str
    type: str
    version: str = "1.0"
    domain: List[str] = Field(default_factory=list)
    sector: List[str] = Field(default_factory=list)
    agent_access: List[str] = Field(default_factory=list)
    confidence: str = "medium"
    source: str = "evangelista"
    last_validated: Optional[date] = None
    parent: Optional[str] = None
    related: List[str] = Field(default_factory=list)
    depends_on: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    status: str = "active"

    # Campos calculados por el parser
    file_path: str
    file_hash: str
    raw_content: str


class Chunk(BaseModel):
    """Fragmento de documento listo para vectorizar e indexar en Qdrant."""

    chunk_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    document_id: str
    document_title: str
    section_header: str
    content: str

    # Metadata heredada del documento padre
    type: str
    domain: List[str]
    sector: List[str]
    agent_access: List[str]
    confidence: str
    source: str
    tags: List[str]
    file_hash: str

    # Embedding (se llena después de generar)
    embedding: List[float] = Field(default_factory=list)

    # Posición en el documento
    chunk_index: int
    total_chunks: int


class SearchResult(BaseModel):
    """Resultado de una búsqueda en el vector store."""

    chunk_id: str
    document_id: str
    document_title: str
    section_header: str
    content: str
    score: float
    metadata: dict
