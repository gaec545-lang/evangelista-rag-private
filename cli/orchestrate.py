"""
CLI del orquestador.

Uso:
    python -m cli.orchestrate "Analiza a Textiles Atoyac"
    python -m cli.orchestrate "Calcula Setup Fee para 3 sucursales y 2 ERPs"
    python -m cli.orchestrate "Diseña modelo dimensional para inventarios" --json
"""
import asyncio
import json
import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

console = Console()


@click.command()
@click.argument("task")
@click.option("--json-output", "as_json", is_flag=True, default=False, help="Output en JSON crudo")
@click.option("--context", "-c", default=None, help="Contexto JSON adicional (string)")
def main(task: str, as_json: bool, context: str):
    """Ejecuta el orquestador de Evangelista & Co. para una TASK."""
    ctx_dict = {}
    if context:
        try:
            ctx_dict = json.loads(context)
        except json.JSONDecodeError:
            console.print("[yellow]⚠ Contexto JSON inválido, ignorando.[/yellow]")

    from src.orchestrator.graph import run_orchestrator
    state = asyncio.run(run_orchestrator(task, context=ctx_dict))

    if as_json:
        click.echo(state.model_dump_json(indent=2))
        return

    # --- Rich output ---
    console.print(Panel(f"[bold]{task}[/bold]", title="[cyan]Orquestador EIP[/cyan]", border_style="cyan"))

    # Subtareas
    table = Table(title="Subtareas ejecutadas", show_lines=True)
    table.add_column("ID", style="dim", width=6)
    table.add_column("Agente", style="bold", width=14)
    table.add_column("Estado", width=12)
    table.add_column("Confianza", width=10)
    table.add_column("Descripción")

    for st in state.subtasks:
        color = "green" if st.status.value == "completed" else "red"
        table.add_row(
            st.id,
            st.assigned_agent,
            f"[{color}]{st.status.value}[/{color}]",
            f"{st.confidence:.2f}",
            st.description[:60] + ("…" if len(st.description) > 60 else ""),
        )

    console.print(table)

    # Respuesta final
    console.print(
        Panel(
            state.final_response or "[dim]Sin respuesta generada[/dim]",
            title="[green]Respuesta sintetizada[/green]",
            border_style="green",
        )
    )

    # Métricas
    metrics = (
        f"Confianza global: [bold]{state.total_confidence:.2f}[/bold] | "
        f"Tiempo: [bold]{state.execution_time_ms}ms[/bold] | "
        f"Subtareas: [bold]{len(state.subtasks)}[/bold] | "
        f"Errores: [bold]{len(state.errors)}[/bold]"
    )
    console.print(f"\n[dim]{metrics}[/dim]")

    if state.sources_used:
        console.print(f"[dim]Fuentes: {', '.join(state.sources_used[:5])}[/dim]")

    if state.errors:
        console.print("\n[yellow]Advertencias:[/yellow]")
        for err in state.errors:
            console.print(f"  [yellow]⚠[/yellow] {err}")


if __name__ == "__main__":
    main()
