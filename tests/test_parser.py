"""Tests para el módulo de parsing de Markdown."""
import pytest
import tempfile
from pathlib import Path

from src.ingestion.parser import MarkdownParser
from src.core.models import VaultDocument

VALID_MD = """---
id: "EVK-TEST-001"
title: "Documento de Prueba"
type: framework
version: "1.0"
domain: [finanzas, procesos]
sector: [manufactura]
agent_access: [financial, all]
confidence: high
source: evangelista
last_validated: 2026-03-28
parent: ""
related: []
depends_on: []
tags: [foundation]
status: active
last_ingested: null
chunk_count: null
---

# Documento de Prueba

## Sección Principal

Contenido de la sección principal con información importante.

## Segunda Sección

Más contenido relevante para los tests.
"""

MISSING_FIELDS_MD = """---
title: "Sin ID"
type: framework
---

# Contenido sin campos obligatorios
"""

INVALID_YAML_MD = """---
id: [invalid: yaml: here
---

# Contenido con YAML inválido
"""

NO_FRONTMATTER_MD = """# Solo Markdown

Sin frontmatter YAML al inicio.
"""


@pytest.fixture
def parser():
    return MarkdownParser()


@pytest.fixture
def temp_md_file():
    """Crea un archivo .md temporal para tests."""
    def _create(content: str) -> Path:
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8"
        )
        tmp.write(content)
        tmp.close()
        return Path(tmp.name)
    return _create


class TestMarkdownParser:
    def test_parse_valid_document(self, parser, temp_md_file):
        path = temp_md_file(VALID_MD)
        doc = parser.parse_file(path)
        assert doc is not None
        assert doc.id == "EVK-TEST-001"
        assert doc.title == "Documento de Prueba"
        assert doc.type == "framework"
        assert "financial" in doc.agent_access
        assert doc.domain == ["finanzas", "procesos"]
        assert "foundation" in doc.tags

    def test_parse_missing_required_fields(self, parser, temp_md_file):
        path = temp_md_file(MISSING_FIELDS_MD)
        doc = parser.parse_file(path)
        assert doc is None

    def test_parse_invalid_yaml(self, parser, temp_md_file):
        path = temp_md_file(INVALID_YAML_MD)
        doc = parser.parse_file(path)
        assert doc is None

    def test_parse_no_frontmatter(self, parser, temp_md_file):
        path = temp_md_file(NO_FRONTMATTER_MD)
        doc = parser.parse_file(path)
        assert doc is None

    def test_raw_content_excludes_frontmatter(self, parser, temp_md_file):
        path = temp_md_file(VALID_MD)
        doc = parser.parse_file(path)
        assert doc is not None
        assert "---" not in doc.raw_content
        assert "Sección Principal" in doc.raw_content

    def test_file_hash_computed(self, parser, temp_md_file):
        path = temp_md_file(VALID_MD)
        doc = parser.parse_file(path)
        assert doc is not None
        assert len(doc.file_hash) == 32  # MD5 hexdigest

    def test_nonexistent_file(self, parser):
        doc = parser.parse_file("/ruta/que/no/existe.md")
        assert doc is None
