"""Tests para el módulo de chunking semántico."""
import pytest
from src.ingestion.chunker import SemanticChunker
from src.core.models import VaultDocument
from src.core.models import Chunk

SAMPLE_CONTENT = """# Título Principal

Introducción del documento.

## Primera Sección

Contenido de la primera sección con información importante sobre el tema.
Esta sección tiene suficiente contenido para ser un chunk válido.

## Segunda Sección

Contenido de la segunda sección con más detalles relevantes.
También tiene suficiente contenido para ser un chunk independiente.

### Subsección

Detalle adicional de la segunda sección.
"""

SHORT_CONTENT = """## Sección Muy Corta

Solo unas pocas palabras.

## Otra Sección

También muy corta.
"""


def make_document(content: str, agent_access: list[str] | None = None) -> VaultDocument:
    return VaultDocument(
        id="EVK-TEST-001",
        title="Documento de Prueba",
        type="framework",
        agent_access=agent_access or ["all"],
        file_path="/tmp/test.md",
        file_hash="abc123",
        raw_content=content,
    )


@pytest.fixture
def chunker():
    return SemanticChunker(min_length=50, max_length=2000)


class TestSemanticChunker:
    def test_chunks_por_headers_h2(self, chunker):
        doc = make_document(SAMPLE_CONTENT)
        chunks = chunker.chunk(doc)
        assert len(chunks) >= 2
        headers = [c.section_header for c in chunks]
        assert any("Primera Sección" in h for h in headers)
        assert any("Segunda Sección" in h for h in headers)

    def test_metadata_heredada(self, chunker):
        doc = make_document(SAMPLE_CONTENT, agent_access=["financial", "analyst"])
        chunks = chunker.chunk(doc)
        for chunk in chunks:
            assert chunk.document_id == "EVK-TEST-001"
            assert chunk.document_title == "Documento de Prueba"
            assert "financial" in chunk.agent_access
            assert chunk.type == "framework"

    def test_chunk_indices(self, chunker):
        doc = make_document(SAMPLE_CONTENT)
        chunks = chunker.chunk(doc)
        for i, chunk in enumerate(chunks):
            assert chunk.chunk_index == i
            assert chunk.total_chunks == len(chunks)

    def test_contexto_prepended(self, chunker):
        doc = make_document(SAMPLE_CONTENT)
        chunks = chunker.chunk(doc)
        for chunk in chunks:
            assert "Documento: Documento de Prueba" in chunk.content
            assert "Sección:" in chunk.content

    def test_chunks_cortos_fusionados(self, chunker):
        doc = make_document(SHORT_CONTENT)
        chunks = chunker.chunk(doc)
        # Los chunks cortos deben fusionarse o al menos no ser vacíos
        for chunk in chunks:
            assert len(chunk.content) > 0

    def test_documento_sin_headers(self, chunker):
        doc = make_document("Texto simple sin ningún header.\nSolo párrafos.")
        chunks = chunker.chunk(doc)
        assert len(chunks) >= 1

    def test_embedding_vacio_por_defecto(self, chunker):
        doc = make_document(SAMPLE_CONTENT)
        chunks = chunker.chunk(doc)
        for chunk in chunks:
            assert chunk.embedding == []
