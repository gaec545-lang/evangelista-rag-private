"""CLI para ingestión del vault al pipeline RAG."""
import asyncio
import time
from pathlib import Path
import click
from rich.console import Console
from rich.table import Table
from rich.progress import track

from src.config import settings
from src.ingestion.parser import MarkdownParser
from src.ingestion.chunker import SemanticChunker
from src.ingestion.embedder import Embedder
from src.ingestion.indexer import Indexer
from src.ingestion.watcher import VaultWatcher
from src.utils.qdrant import close_qdrant_client

console = Console()


async def ingest_file(
    file_path: str,
    parser: MarkdownParser,
    chunker: SemanticChunker,
    embedder: Embedder,
    indexer: Indexer,
) -> tuple[bool, int]:
    """Ingesta un solo archivo .md. Retorna (indexado, num_chunks)."""
    doc = parser.parse_file(file_path)
    if doc is None:
        return False, 0

    chunks = chunker.chunk(doc)
    if not chunks:
        return False, 0

    texts = [c.content for c in chunks]
    embeddings = await embedder.embed_batch(texts)
    for chunk, emb in zip(chunks, embeddings):
        chunk.embedding = emb

    indexed = indexer.upsert_chunks(chunks)
    return indexed, len(chunks)


async def ingest_vault(vault_path: str) -> dict:
    """Ingesta todo el vault. Retorna estadísticas."""
    parser = MarkdownParser()
    chunker = SemanticChunker()
    embedder = Embedder()
    indexer = Indexer()
    indexer.ensure_collection()

    docs = parser.parse_directory(vault_path)
    console.print(f"[cyan]Documentos encontrados:[/cyan] {len(docs)}")

    stats = {"procesados": 0, "indexados": 0, "saltados": 0, "chunks_totales": 0, "errores": 0}

    for doc in track(docs, description="Ingestando documentos..."):
        try:
            chunks = chunker.chunk(doc)
            if not chunks:
                stats["saltados"] += 1
                continue

            texts = [c.content for c in chunks]
            embeddings = await embedder.embed_batch(texts)
            for chunk, emb in zip(chunks, embeddings):
                chunk.embedding = emb

            indexed = indexer.upsert_chunks(chunks)
            stats["procesados"] += 1
            if indexed:
                stats["indexados"] += 1
                stats["chunks_totales"] += len(chunks)
            else:
                stats["saltados"] += 1
        except Exception as e:
            console.print(f"[red]Error en {doc.id}:[/red] {e}")
            stats["errores"] += 1

    return stats


@click.command()
@click.option("--vault-path", default=None, help="Ruta al Obsidian Vault")
@click.option("--file", default=None, help="Ingestar un solo archivo .md")
@click.option("--stats", is_flag=True, help="Mostrar estadísticas de la colección")
@click.option("--watch", is_flag=True, help="Modo watch: re-ingesta al detectar cambios")
def main(vault_path, file, stats, watch):
    """Ingestión de documentos del Evangelista Vault al pipeline RAG."""
    vault = vault_path or settings.VAULT_PATH

    if stats:
        indexer = Indexer()
        info = indexer.collection_stats()
        table = Table(title="Estadísticas de la Colección Qdrant")
        table.add_column("Campo", style="cyan")
        table.add_column("Valor", style="green")
        for k, v in info.items():
            table.add_row(str(k), str(v))
        console.print(table)
        return

    if file:
        parser = MarkdownParser()
        chunker = SemanticChunker()
        embedder = Embedder()
        indexer = Indexer()
        indexer.ensure_collection()

        async def _ingest_single():
            indexed, n = await ingest_file(file, parser, chunker, embedder, indexer)
            if indexed:
                console.print(f"[green]Indexado:[/green] {file} ({n} chunks)")
            else:
                console.print(f"[yellow]Saltado (sin cambios o inválido):[/yellow] {file}")

        asyncio.run(_ingest_single())
        return

    if watch:
        console.print(f"[bold cyan]Modo watch activo:[/bold cyan] {vault}")
        parser = MarkdownParser()
        chunker = SemanticChunker()
        embedder = Embedder()
        indexer = Indexer()
        indexer.ensure_collection()

        def on_ingest(path: str) -> None:
            async def _run():
                indexed, n = await ingest_file(path, parser, chunker, embedder, indexer)
                if indexed:
                    console.print(f"[green]Re-indexado:[/green] {Path(path).name} ({n} chunks)")

            asyncio.run(_run())

        def on_delete(path: str) -> None:
            console.print(f"[red]Archivo eliminado:[/red] {Path(path).name}")

        watcher = VaultWatcher(vault, on_ingest, on_delete)
        watcher.start()
        try:
            while True:
                pending = watcher.get_pending()
                for p in pending:
                    on_ingest(p)
                time.sleep(1)
        except KeyboardInterrupt:
            watcher.stop()
        return

    # Ingestión completa del vault
    console.print(f"[bold]Ingestando vault:[/bold] {vault}")
    try:
        result = asyncio.run(ingest_vault(vault))

        table = Table(title="Resultado de Ingestión")
        table.add_column("Métrica", style="cyan")
        table.add_column("Valor", style="green")
        for k, v in result.items():
            table.add_row(k, str(v))
        console.print(table)
    except Exception as e:
        console.print(f"[red]Error inesperado:[/red] {e}")
    finally:
        close_qdrant_client()


if __name__ == "__main__":
    main()
