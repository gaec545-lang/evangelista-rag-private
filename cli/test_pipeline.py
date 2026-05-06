"""Test end-to-end del pipeline RAG completo."""
import asyncio
from pathlib import Path
import click
from rich.console import Console
from rich.panel import Panel

from src.ingestion.parser import MarkdownParser
from src.ingestion.chunker import SemanticChunker
from src.ingestion.embedder import Embedder
from src.ingestion.indexer import Indexer
from src.retrieval.query_engine import QueryEngine
from src.llm.factory import get_llm_client
from src.config import settings

console = Console()

TEST_QUERY = "¿Qué es ALCOA+ y cómo lo aplica Evangelista en Foundation?"
TEST_AGENT = "all"
VALIDATION_KEYWORD = "Certificado"

SYSTEM_PROMPT = """Eres el asistente de conocimiento de Evangelista & Co., una firma de Intelligence Architecture en Puebla, México.
Responde ÚNICAMENTE basándote en el contexto proporcionado. Si la información no está en el contexto, di que no tienes esa información.
Responde en español de México. Sé preciso y usa los datos específicos del contexto (números, porcentajes, reglas)."""


async def run_test(vault_path: str) -> bool:
    """Ejecuta el test end-to-end. Retorna True si pasa."""
    console.rule("[bold cyan]Test E2E — Evangelista RAG Pipeline")

    # 1. Parsear el documento de prueba
    test_file = Path(vault_path) / "frameworks" / "alcoa-plus" / "alcoa-protocol.md"
    console.print(f"\n[1/5] Parseando: [cyan]{test_file.name}[/cyan]")

    parser = MarkdownParser()
    doc = parser.parse_file(test_file)
    if doc is None:
        console.print("[red]FALLO: No se pudo parsear el documento[/red]")
        return False
    console.print(f"[green]OK[/green] Documento parseado: {doc.id} | {len(doc.raw_content)} chars")

    # 2. Chunking
    console.print("\n[2/5] Chunkeando...")
    chunker = SemanticChunker()
    chunks = chunker.chunk(doc)
    console.print(f"[green]OK[/green] {len(chunks)} chunks generados")

    # 3. Embeddings
    console.print("\n[3/5] Generando embeddings (Ollama)...")
    embedder = Embedder()
    health = await embedder.health_check()
    if not health:
        console.print("[yellow]AVISO: Ollama no disponible — saltando test de embeddings[/yellow]")
        console.print("[yellow]  Asegúrate de tener Ollama corriendo: ollama serve[/yellow]")
        console.print("[yellow]  Y el modelo instalado: ollama pull nomic-embed-text[/yellow]")
        return False

    texts = [c.content for c in chunks]
    embeddings = await embedder.embed_batch(texts)
    for chunk, emb in zip(chunks, embeddings):
        chunk.embedding = emb
    console.print(f"[green]OK[/green] Embeddings de dim={len(embeddings[0])} generados")

    # 4. Indexar
    console.print("\n[4/5] Indexando en Qdrant...")
    indexer = Indexer()
    try:
        indexer.ensure_collection()
        indexer.upsert_chunks(chunks)
        stats = indexer.collection_stats()
        console.print(
            f"[green]OK[/green] Colección: {stats.get('total_points', '?')} puntos totales"
        )
    except Exception as e:
        console.print(f"[yellow]AVISO: Qdrant no disponible: {e}[/yellow]")
        console.print("[yellow]  Levanta Qdrant con: docker compose up -d[/yellow]")
        return False

    # 5. Search + LLM
    console.print(f"\n[5/5] Search + LLM con query: [italic]{TEST_QUERY}[/italic]")
    engine = QueryEngine(embedder=embedder)
    results = await engine.search(query=TEST_QUERY, agent_name=TEST_AGENT, final_k=3)

    if not results:
        console.print("[red]FALLO: No se recuperaron chunks[/red]")
        return False

    context = engine.format_context(results)
    prompt = f"Contexto de la base de conocimiento:\n\n{context}\n\nPregunta: {TEST_QUERY}"

    llm = get_llm_client()
    try:
        response = await llm.generate(prompt=prompt, system_prompt=SYSTEM_PROMPT)
    except Exception as e:
        console.print(f"[yellow]AVISO: LLM no disponible: {e}[/yellow]")
        return False

    console.print(Panel(response, title="[bold]Respuesta del LLM[/bold]", expand=False))

    # Validar respuesta
    passed = VALIDATION_KEYWORD.lower() in response.lower()
    if passed:
        console.print(
            f"\n[bold green]TEST PASADO[/bold green] — La respuesta menciona '{VALIDATION_KEYWORD}'"
        )
    else:
        console.print(
            f"\n[bold red]TEST FALLÓ[/bold red] — La respuesta NO menciona '{VALIDATION_KEYWORD}'"
        )

    # Mostrar chunks usados
    console.print("\n[dim]Chunks recuperados:[/dim]")
    for r in results:
        console.print(f"  • {r.document_title} — {r.section_header} (score: {r.score:.3f})")

    return passed


@click.command()
@click.option("--vault-path", default=None, help="Ruta al Obsidian Vault")
def main(vault_path):
    """Test end-to-end del pipeline RAG de Evangelista."""
    vault = vault_path or settings.VAULT_PATH
    success = asyncio.run(run_test(vault))
    raise SystemExit(0 if success else 1)


if __name__ == "__main__":
    main()
