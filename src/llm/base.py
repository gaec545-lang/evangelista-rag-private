"""Interfaz abstracta para todos los clientes LLM."""
from abc import ABC, abstractmethod


class LLMClient(ABC):
    """Interfaz agnóstica para cualquier proveedor de LLM."""

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = 0.3,
        max_tokens: int = 2000,
    ) -> str:
        """Genera texto a partir de un prompt."""
        ...

    @abstractmethod
    async def embed(self, text: str) -> list[float]:
        """
        Genera el embedding de un texto.
        Para providers que no tienen embeddings propios (Groq, Anthropic),
        delega a Ollama con nomic-embed-text.
        """
        ...
