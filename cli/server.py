"""
Levanta el servidor FastAPI de Evangelista Intelligence Platform.

Uso:
    python -m cli.server
    python -m cli.server --port 8080 --reload
"""
import click
import uvicorn


@click.command()
@click.option("--host", default="0.0.0.0", show_default=True, help="Host de escucha")
@click.option("--port", default=8001, show_default=True, help="Puerto")
@click.option("--reload", is_flag=True, default=False, help="Hot-reload (solo desarrollo)")
@click.option("--workers", default=1, show_default=True, help="Número de workers")
def main(host: str, port: int, reload: bool, workers: int):
    """Levanta el servidor FastAPI de Evangelista Intelligence Platform."""
    click.echo(f"Iniciando Evangelista Intelligence Platform en http://{host}:{port}")
    click.echo(f"Docs: http://{host}:{port}/docs")
    uvicorn.run(
        "src.api.server:app",
        host=host,
        port=port,
        reload=reload,
        workers=workers if not reload else 1,
        log_level="info",
    )


if __name__ == "__main__":
    main()
