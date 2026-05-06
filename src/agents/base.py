from abc import ABC, abstractmethod
import yaml
import json
import re
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
import structlog
from src.llm.factory import get_llm_client
from src.retrieval.query_engine import QueryEngine

logger = structlog.get_logger(__name__)

@dataclass
class AgentOutput:
    """Standardized output for all agents."""
    agent_name: str
    confidence: float = field(default=0.0)
    analysis: str = ""
    recommendations: List[str] = field(default_factory=list)
    data_points: List[Dict[str, Any]] = field(default_factory=list)
    sources_used: List[str] = field(default_factory=list)
    escalation_needed: bool = False
    escalation_reason: Optional[str] = None
    escalation_target: Optional[str] = None

class BaseAgent(ABC):
    """Clase base para todos los agentes especialistas."""

    def __init__(self, name: str, prompt_document_id: str):
        """
        Args:
            name: Identificador único del agente.
            prompt_document_id: ID del documento en el obsidian vault (e.g. EVK-AG-001).
        """
        self.name = name
        self.prompt_document_id = prompt_document_id
        self.llm = get_llm_client()
        self._system_prompt: Optional[str] = None
        self.query_engine = QueryEngine()

    async def _load_prompt(self) -> str:
        """Carga el system prompt desde el vault via RAG."""
        if self._system_prompt:
            return self._system_prompt

        logger.info("loading_agent_prompt", agent=self.name, doc_id=self.prompt_document_id)
        
        # Buscamos el documento específico por su ID
        results = await self.query_engine.search(
            query=f"id:{self.prompt_document_id} system prompt {self.name}",
            agent_name="all",
            top_k=3,
            final_k=1
        )

        if results:
            self._system_prompt = results[0].content
            logger.info("prompt_loaded_from_vault", agent=self.name, doc_id=self.prompt_document_id)
        else:
            # Fallback a un prompt base si no se encuentra en el vault
            logger.warning("prompt_not_found_in_vault", agent=self.name, doc_id=self.prompt_document_id)
            self._system_prompt = f"Eres el agente {self.name} de Evangelista & Co. Tu objetivo es ayudar en tareas de consultoría."

        return self._system_prompt

    async def _get_rag_context(self, task: str) -> tuple[list, str]:
        """Obtiene contexto del RAG. Retorna (resultados, contexto_texto)."""
        try:
            results = await self.query_engine.search(
                query=task,
                agent_name=self.name,
                top_k=10,
                final_k=5
            )
            
            if results:
                context_text = "\n\n---\n\n".join([
                    f"**Fuente: {r.document_title}** (relevancia: {r.score:.2f})\n"
                    f"Sección: {r.section_header}\n\n"
                    f"{r.content}"
                    for r in results
                ])
                return results, context_text
            else:
                return [], "No se encontraron documentos relevantes en el knowledge base para esta consulta."
                
        except Exception as e:
            import structlog
            structlog.get_logger().error("agent_rag_failed", agent=self.name, error=str(e))
            return [], "Error al consultar el knowledge base. Respondiendo con conocimiento general del agente."

    async def execute(self, task: str, context: Optional[List[dict]] = None) -> AgentOutput:
        """Execute a task with optional RAG context."""
        from src.llm.factory import get_llm_client

        # 1. SIEMPRE buscar en RAG primero (a menos que venga contexto pre-inyectado)
        if context is None:
            rag_results, context_text = await self._get_rag_context(task)
        else:
            rag_results = []
            context_text = "\n\n".join([
                f"**{c.get('title', 'Contexto')}**\n{c.get('content', '')}"
                for c in context
            ])

        # 2. Construir prompt con contexto
        full_prompt = f"""## Contexto del knowledge base de Evangelista & Co.

{context_text}

## Tarea asignada

{task}

Responde siguiendo estrictamente tu formato de output definido en el system prompt. Usa las fuentes del knowledge base cuando sean relevantes y cítalas."""

        # 3. Llamar al LLM
        client = get_llm_client()
        response_text = await client.generate(
            prompt=full_prompt,
            system_prompt=await self._load_prompt(),
            temperature=0.3
        )

        # 4. Construir output estandarizado
        # Cada especialista puede sobrescribir execute para validaciones específicas
        return AgentOutput(
            agent_name=self.name,
            confidence=0.8,
            analysis=response_text,
            sources_used=[r.document_id for r in rag_results] if rag_results else [],
            recommendations=[]
        )

    @property
    @abstractmethod
    def domains(self) -> List[str]:
        """Functional domains covered by this agent."""
        ...

    @property
    @abstractmethod
    def tools(self) -> List[str]:
        """Tools available to this agent."""
        ...
