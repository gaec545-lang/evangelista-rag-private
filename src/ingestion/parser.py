"""Parser de archivos Markdown del Obsidian Vault."""
import re
from pathlib import Path
from typing import Optional
import yaml

from src.core.models import VaultDocument
from src.utils.logger import get_logger
from src.utils.hashing import compute_file_hash

logger = get_logger(__name__)

REQUIRED_FIELDS = {"id", "title", "type", "agent_access"}

FRONTMATTER_PATTERN = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


class MarkdownParser:
    """Parsea archivos .md del vault extrayendo frontmatter YAML y cuerpo."""

    def parse_file(self, file_path: str | Path) -> Optional[VaultDocument]:
        """
        Parsea un archivo .md y retorna un VaultDocument.
        Retorna None si el archivo no tiene frontmatter válido o faltan campos obligatorios.
        """
        path = Path(file_path)
        try:
            raw = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            # ponytail: utf-8 failed, try cp1252 for emojis/windows quirks
            raw = path.read_text(encoding="cp1252")
        except OSError as e:
            logger.warning("error_leyendo_archivo", path=str(path), error=str(e))
            return None

        frontmatter, body = self._split_frontmatter(raw)
        if frontmatter is None:
            logger.warning("sin_frontmatter", path=str(path))
            return None

        try:
            metadata = yaml.safe_load(frontmatter)
        except yaml.YAMLError as e:
            logger.warning("yaml_invalido", path=str(path), error=str(e))
            return None

        if not isinstance(metadata, dict):
            logger.warning("yaml_no_es_dict", path=str(path))
            return None

        missing = REQUIRED_FIELDS - set(metadata.keys())
        if missing:
            logger.warning("campos_obligatorios_faltantes", path=str(path), missing=list(missing))
            return None

        # Normalizar campos que pueden ser None
        for list_field in ["domain", "sector", "agent_access", "related", "depends_on", "tags"]:
            if metadata.get(list_field) is None:
                metadata[list_field] = []

        file_hash = compute_file_hash(path)

        try:
            doc = VaultDocument(
                **{k: v for k, v in metadata.items() if k not in ("last_ingested", "chunk_count")},
                file_path=str(path.resolve()),
                file_hash=file_hash,
                raw_content=body.strip(),
            )
        except Exception as e:
            logger.warning("error_construyendo_documento", path=str(path), error=str(e))
            return None

        logger.info("documento_parseado", id=doc.id, title=doc.title, chunks_aprox=len(body) // 500)
        return doc

    def parse_directory(
        self,
        vault_path: str | Path,
        skip_prefixes: tuple[str, ...] = ("_templates",),
    ) -> list[VaultDocument]:
        """
        Parsea todos los .md del vault recursivamente.
        Ignora directorios en skip_prefixes y archivos que empiezan con punto.
        Los archivos _moc-*.md SI se ingeestan.
        """
        vault = Path(vault_path)
        documents: list[VaultDocument] = []

        for md_file in sorted(vault.rglob("*.md")):
            # Ignorar archivos en directorios excluidos
            relative = md_file.relative_to(vault)
            parts = relative.parts

            skip = False
            for part in parts[:-1]:  # solo directorios, no el archivo mismo
                if part in skip_prefixes:
                    skip = True
                    break
                if part.startswith("."):
                    skip = True
                    break

            if skip:
                continue

            # Ignorar archivos ocultos pero NO los _moc-*.md
            filename = md_file.name
            if filename.startswith("."):
                continue
            if filename.startswith("_") and not filename.startswith("_moc-"):
                continue

            doc = self.parse_file(md_file)
            if doc is not None:
                documents.append(doc)

        logger.info("directorio_parseado", vault=str(vault), total_documentos=len(documents))
        return documents

    def _split_frontmatter(self, raw: str) -> tuple[Optional[str], str]:
        """Separa el frontmatter YAML del cuerpo Markdown."""
        match = FRONTMATTER_PATTERN.match(raw)
        if not match:
            return None, raw
        frontmatter = match.group(1)
        body = raw[match.end():]
        return frontmatter, body
