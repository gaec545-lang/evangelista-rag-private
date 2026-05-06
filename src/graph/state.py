"""
Estado unificado del grafo Advanced RAG.

Viaja por TODOS los nodos. Cada nodo lee partes específicas y retorna
un nuevo diccionario con solo los campos que modifica (patrón LangGraph).

Ciclos posibles:
    1. Retriever → Grader → (not relevant) → Web Searcher → Grader → Generator
    2. Generator → Hallucination Check → (hallucinated) → Generator   [max_retries]
    3. Quality Check → (not useful) → Retriever                        [max_retries]
"""
from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Optional, Literal
from enum import Enum


class NodeStatus(str, Enum):
    PENDING   = "pending"
    RUNNING   = "running"
    COMPLETED = "completed"
    FAILED    = "failed"
    RETRYING  = "retrying"


class RetrievedDocument(BaseModel):
    """Un documento recuperado del RAG o de la web."""
    id: str
    title: str
    content: str
    source: Literal["qdrant", "web", "tool"]
    score: float = 0.0
    # CRAG — asignado por grader.py
    relevant: Optional[bool] = None          # None = sin evaluar
    grader_reasoning: Optional[str] = None


class GraphState(BaseModel):
    """
    Estado completo del grafo cíclico de Advanced RAG.

    Filosofía:
        - Inmutable salvo por el nodo que lo procesa.
        - Cada nodo retorna dict{campo: nuevo_valor} — LangGraph hace el merge.
        - No hay side-effects fuera del estado.
    """

    # ─── INPUT ────────────────────────────────────────────────────────────────
    question: str                                       # Pregunta original del usuario
    context: dict = Field(default_factory=dict)         # Metadata de sesión / cliente
    thread_id: str = "default"                          # ID de sesión para trazabilidad

    # ─── ROUTING ──────────────────────────────────────────────────────────────
    route: Optional[Literal["rag", "tools", "web", "multi"]] = None
    route_reasoning: str = ""

    # ─── RETRIEVAL ────────────────────────────────────────────────────────────
    documents: list[RetrievedDocument] = Field(default_factory=list)
    web_results: list[RetrievedDocument] = Field(default_factory=list)

    # ─── CRAG (Corrective RAG) ────────────────────────────────────────────────
    relevant_documents: list[RetrievedDocument] = Field(default_factory=list)
    needs_web_search: bool = False
    crag_action: Optional[Literal["use_docs", "refine_query", "web_search"]] = None
    refined_query: Optional[str] = None                 # Query refinada si CRAG decide refinar

    # ─── TOOL EXECUTION ───────────────────────────────────────────────────────
    tool_results: dict[str, str] = Field(default_factory=dict)

    # ─── GENERATION ───────────────────────────────────────────────────────────
    generation: str = ""
    generation_sources: list[str] = Field(default_factory=list)

    # ─── SELF-REFLECTIVE RAG ──────────────────────────────────────────────────
    hallucination_check: Optional[bool] = None          # True = grounded | False = hallucinated
    hallucination_reasoning: str = ""
    quality_check: Optional[bool] = None                # True = útil | False = no responde
    quality_reasoning: str = ""

    # ─── SYNTHESIS ────────────────────────────────────────────────────────────
    final_response: str = ""
    confidence: float = 0.0

    # ─── META ─────────────────────────────────────────────────────────────────
    current_node: str = ""
    node_history: list[str] = Field(default_factory=list)
    retry_count: int = 0
    max_retries: int = 2
    errors: list[str] = Field(default_factory=list)
    execution_time_ms: int = 0

    # ─── MERMAID LOG (para /api/v1/graph/state/{id}) ──────────────────────────
    mermaid_log: list[dict] = Field(default_factory=list)
    # Formato: [{"node": "router", "status": "completed", "timestamp": "...", "detail": "..."}]

    def log_node(self, node: str, status: NodeStatus, detail: str = "") -> dict:
        """Helper para construir una entrada del mermaid_log."""
        from datetime import datetime, timezone
        return {
            "node": node,
            "status": status.value,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "detail": detail,
        }
