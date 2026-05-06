import os
from typing import Any, Dict, Optional
from .base import BaseAgent, AgentOutput
from src.agents.registry import AgentRegistry
import structlog

logger = structlog.get_logger()

class DataEngineerAgent(BaseAgent):
    """Agente especializado en estructuras de datos, SQL y ETL."""

    def __init__(self):
        super().__init__(
            name="data_engineer",
            prompt_document_id="EVK-AG-DAT-001"
        )

    @property
    def domains(self) -> list[str]:
        return ["datos", "inventarios", "produccion"]

    @property
    def tools(self) -> list[str]:
        return ["rag_query", "generate_sql", "generate_python", "format_table"]

    async def execute(self, task: str, context: list[dict] = None) -> AgentOutput:
        # 1. SIEMPRE buscar en RAG primero
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

Responde siguiendo estrictamente tu formato de output definido. Usa las fuentes del knowledge base cuando sean relevantes y cítalas."""
        
        # 3. Llamar al LLM
        from src.llm.factory import get_llm_client
        client = get_llm_client()
        response = await client.generate(
            prompt=full_prompt,
            system_prompt=await self._load_prompt(),
            temperature=0.3
        )
        
        # 4. Construir output con validación
        result = AgentOutput(
            agent_name=self.name,
            confidence=self._estimate_confidence(response),
            analysis=response,
            sources_used=[r.document_id for r in rag_results] if rag_results else [],
            recommendations=self._extract_recommendations(response),
            escalation_needed=False,
            escalation_reason=None
        )
        
        if self._should_escalate(response):
            result.escalation_needed = True
            result.escalation_reason = self._extract_escalation_reason(response)
        
        return result

    def _estimate_confidence(self, response: str) -> float:
        confidence: float = 0.8
        uncertainty_phrases = ["no tengo información", "necesito más datos", "no es posible diseñar", "información insuficiente"]
        for phrase in uncertainty_phrases:
            if phrase.lower() in response.lower():
                confidence -= 0.15
        if "tabla" in response.lower() or "sql" in response.lower() or "etl" in response.lower() or "modelo" in response.lower():
            confidence += 0.05
        return max(0.3, min(1.0, confidence))

    def _should_escalate(self, response: str) -> bool:
        if "necesito confirmar" in response.lower() or "para afinarlo" in response.lower():
            return False
        
        other_domain_keywords = ["setup fee", "success fee", "pricing", "rediseño de proceso", "six sigma", "dmaic"]
        for kw in other_domain_keywords:
            if kw.lower() in response.lower():
                return True
        return False

    def _extract_escalation_reason(self, response: str) -> str:
        if "sugiero agente" in response.lower():
            idx = response.lower().index("sugiero agente")
            return response[idx:idx+100].strip()
        return "Tarea fuera del dominio de ingeniería de datos — requiere otro especialista"

    def _extract_recommendations(self, response: str) -> list[str]:
        recommendations = []
        lines = response.split("\n")
        in_rec_section = False
        for line in lines:
            if "recomendaciones" in line.lower() or "recomiendo" in line.lower():
                in_rec_section = True
                continue
            if in_rec_section and line.strip().startswith(("1.", "2.", "3.", "4.", "5.", "-", "*")):
                recommendations.append(line.strip().lstrip("0123456789.-* "))
            elif in_rec_section and line.strip() == "":
                in_rec_section = False
        return recommendations[:5]

# Auto‑register the agent
AgentRegistry.register(DataEngineerAgent())
