"""Chunking semántico por headers Markdown para el pipeline RAG."""
import re
from typing import List
from src.core.models import VaultDocument, Chunk
from src.utils.logger import get_logger
from src.config import settings

logger = get_logger(__name__)

H2_PATTERN = re.compile(r"^## (.+)$", re.MULTILINE)
H3_PATTERN = re.compile(r"^### (.+)$", re.MULTILINE)


class SemanticChunker:
    """
    Divide documentos en chunks semánticos usando la estructura de headers Markdown.
    Cada sección ## es un chunk independiente con su contexto prepended.
    """

    def __init__(
        self,
        min_length: int = settings.CHUNK_MIN_LENGTH,
        max_length: int = settings.CHUNK_MAX_LENGTH,
    ) -> None:
        self.min_length = min_length
        self.max_length = max_length

    def chunk(self, document: VaultDocument) -> list[Chunk]:
        """
        Genera chunks semánticos a partir de un VaultDocument.
        Retorna lista de Chunk con metadata del documento padre.
        """
        sections = self._split_by_h2(document.raw_content)

        if not sections:
            # Si no hay headers ##, el documento completo es un chunk
            sections = [("Documento completo", document.raw_content)]

        raw_chunks: list[tuple[str, str]] = []
        for header, content in sections:
            if len(content) > self.max_length:
                sub = self._split_by_h3(content)
                for sub_header, sub_content in sub:
                    effective_header = f"{header} — {sub_header}" if sub_header else header
                    raw_chunks.extend(self._split_by_paragraph(effective_header, sub_content))
            else:
                raw_chunks.append((header, content))

        # Fusionar chunks demasiado cortos
        merged = self._merge_short_chunks(raw_chunks)

        chunks: list[Chunk] = []
        total = len(merged)
        for idx, (header, content) in enumerate(merged):
            full_text = f"Documento: {document.title}\nSección: {header}\n\n{content.strip()}"
            chunk = Chunk(
                document_id=document.id,
                document_title=document.title,
                section_header=header,
                content=full_text,
                type=document.type,
                domain=document.domain,
                sector=document.sector,
                agent_access=document.agent_access,
                confidence=document.confidence,
                source=document.source,
                tags=document.tags,
                file_hash=document.file_hash,
                chunk_index=idx,
                total_chunks=total,
            )
            chunks.append(chunk)

        logger.info("documento_chunkeado", doc_id=document.id, total_chunks=total)
        return chunks

    def _split_by_h2(self, content: str) -> list[tuple[str, str]]:
        """Divide el contenido por headers ## retornando (header, texto_de_sección)."""
        parts = H2_PATTERN.split(content)
        # parts = [texto_previo, header1, contenido1, header2, contenido2, ...]
        sections: list[tuple[str, str]] = []

        # Texto antes del primer header (introducción del documento)
        intro = parts[0].strip()
        if intro:
            sections.append(("Introducción", intro))

        # Pares header+contenido
        for i in range(1, len(parts), 2):
            header = parts[i].strip()
            body = parts[i + 1].strip() if i + 1 < len(parts) else ""
            if body:
                sections.append((header, body))

        return sections

    def _split_by_h3(self, content: str) -> list[tuple[str, str]]:
        """Divide una sección por headers ### cuando es demasiado larga."""
        parts = H3_PATTERN.split(content)
        sections: list[tuple[str, str]] = []

        intro = parts[0].strip()
        if intro:
            sections.append(("", intro))

        for i in range(1, len(parts), 2):
            header = parts[i].strip()
            body = parts[i + 1].strip() if i + 1 < len(parts) else ""
            if body:
                sections.append((header, body))

        return sections if sections else [("", content)]

    def _split_by_paragraph(self, header: str, content: str) -> list[tuple[str, str]]:
        """Divide contenido muy largo por párrafos doble newline."""
        if len(content) <= self.max_length:
            return [(header, content)]

        paragraphs = re.split(r"\n\n+", content)
        chunks: list[tuple[str, str]] = []
        current = ""
        for para in paragraphs:
            if len(current) + len(para) + 2 > self.max_length and current:
                chunks.append((header, current.strip()))
                current = para
            else:
                current = f"{current}\n\n{para}" if current else para

        if current.strip():
            chunks.append((header, current.strip()))

        return chunks if chunks else [(header, content[: self.max_length])]

    def _merge_short_chunks(self, chunks: list[tuple[str, str]]) -> list[tuple[str, str]]:
        """Fusiona chunks muy cortos con el siguiente chunk."""
        if not chunks:
            return chunks

        merged: list[tuple[str, str]] = []
        buffer_header, buffer_content = chunks[0]

        for header, content in chunks[1:]:
            if len(buffer_content) < self.min_length:
                buffer_content = f"{buffer_content}\n\n{content}"
                buffer_header = f"{buffer_header} | {header}"
            else:
                merged.append((buffer_header, buffer_content))
                buffer_header, buffer_content = header, content

        merged.append((buffer_header, buffer_content))
        return merged
