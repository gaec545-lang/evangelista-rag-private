"""CLI para búsqueda en el pipeline RAG."""
import asyncio
import click
from rich.console import Console
from rich.panel import Panel

from src.retrieval.query_engine import QueryEngine
from src.ingestion.embedder import Embedder
from src.config import settings

console = Console()

VALID_AGENTS = [
    "financial", "process", "data_eng", "risk", "analyst",
    "pm", "hr", "researcher", "all",
]


@click.command()
@click.argument("query")
@click.option(
    "--agent",
    required=True,
    help=f"Nombre del agente. Opciones: {', '.join(VALID_AGENTS)}",
)
@click.option("--domain", multiple=True, help="Filtrar por dominio (ej: finanzas, procesos)")
@click.option("--sector", multiple=True, help="Filtrar por sector (ej: textiles, manufactura)")
@click.option("--type", "doc_type", multiple=True, help="Filtrar por tipo (ej: framework, formula)")
@click.option("--top-k", default=settings.RETRIEVAL_FINAL_K, help="Número de resultados")
def main(query, agent, domain, sector, doc_type, top_k):
    """Busca en el Evangelista Knowledge Base como un agente específico."""
    if agent not in VALID_AGENTS:
        console.print(
            f"[red]Agente inválido:[/red] {agent}. Opciones: {', '.join(VALID_AGENTS)}"
        )
        raise SystemExit(1)

    async def _search():
        embedder = Embedder()
        engine = QueryEngine(embedder=embedder)

        results = await engine.search(
            query=query,
            agent_name=agent,
            domain_filter=list(domain) or None,
            sector_filter=list(sector) or None,
            type_filter=list(doc_type) or None,
            final_k=top_k,
        )

        console.print(f"\n[bold cyan]Query:[/bold cyan] {query}")
        console.print(f"[bold cyan]Agente:[/bold cyan] {agent}")
        console.print(f"[bold cyan]Resultados:[/bold cyan] {len(results)}\n")

        if not results:
            console.print("[yellow]No se encontraron resultados relevantes.[/yellow]")
            return

        for i, r in enumerate(results, 1):
            panel_content = (
                f"[dim]Doc ID:[/dim] {r.document_id}  |  "
                f"[dim]Tipo:[/dim] {r.metadata.get('type', 'N/A')}  |  "
                f"[dim]Score:[/dim] {r.score:.4f}\n\n"
                f"{r.content[:600]}{'...' if len(r.content) > 600 else ''}"
            )
            console.print(
                Panel(
                    panel_content,
                    title=(
                        f"[bold green][{i}] {r.document_title} — {r.section_header}[/bold green]"
                    ),
                    expand=False,
                )
            )

    asyncio.run(_search())


if __name__ == "__main__":
    main()
