import asyncio
import click
import structlog
from typing import List
from src.llm.factory import get_llm_client
from src.llm.config import MODELS

logger = structlog.get_logger()

@click.group()
def cli():
    """Herramientas de gestión y prueba de modelos LLM."""
    pass

@cli.command()
@click.option("--prompt", "-p", required=True, help="Prompt de prueba para enviar a los modelos.")
@click.option("--models", "-m", help="Lista de modelos separados por coma (ej: groq-llama-70b,sambanova-llama). Si no se especifica, usa todos.")
@click.option("--system", "-s", default="Eres un asistente experto en consultoría para PyMEs.", help="System prompt a utilizar.")
def compare(prompt: str, models: str, system: str):
    """Compara múltiples modelos LLM con un mismo prompt."""
    
    model_list = models.split(",") if models else list(MODELS.keys())
    
    async def run_comparison():
        tasks = []
        for model_name in model_list:
            client = get_llm_client(model_name)
            tasks.append(client.generate(prompt=prompt, system_prompt=system))
            
        click.echo(f"\n--- Comparando {len(model_list)} modelos ---\n")
        
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        
        for name, response in zip(model_list, responses):
            click.secho(f"=== MODELO: {name} ===", fg="green", bold=True)
            if isinstance(response, Exception):
                click.secho(f"Error: {str(response)}", fg="red")
            else:
                click.echo(response)
            click.echo("-" * 40)

    asyncio.run(run_comparison())

@cli.command()
def list_models():
    """Enumera los modelos configurados en el sistema."""
    click.echo("\nModelos configurados en Evangelista Intelligence Platform:\n")
    for name, config in MODELS.items():
        click.echo(f"- {name:20} | Provider: {config.provider:15} | Model ID: {config.model_id}")
    click.echo("\nUsa --model <nombre> en tus consultas para cambiar de modelo.\n")

if __name__ == "__main__":
    cli()
