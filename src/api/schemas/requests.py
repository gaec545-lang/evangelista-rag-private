"""Modelos Pydantic para requests y responses de la API."""
from pydantic import BaseModel, Field
from typing import Any


class AnalyzeRequest(BaseModel):
    task: str = Field(..., min_length=5, description="Tarea a analizar")
    context: dict[str, Any] = Field(default_factory=dict, description="Metadata adicional")


class AnalyzeResponse(BaseModel):
    status: str
    response: str
    confidence: float
    sources: list[str]
    execution_time_ms: int
    errors: list[str]
    subtasks: list[dict] = Field(default_factory=list)
    # Nuevos campos para Advanced RAG
    route: str = "unknown"
    node_history: list[str] = Field(default_factory=list)
    mermaid_trace: str = ""
    retry_count: int = 0


class AgentExecuteRequest(BaseModel):
    task: str = Field(..., min_length=1, description="Tarea para el agente")
    context: list[dict] = Field(default_factory=list, description="Contexto RAG adicional")


class AgentExecuteResponse(BaseModel):
    agent: str
    confidence: float
    analysis: str
    recommendations: list[str]
    sources: list[str]
    escalation: bool
    escalation_reason: str | None = None


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=3)
    agent: str = Field(default="all")
    top_k: int = Field(default=5, ge=1, le=20)


class SearchResponse(BaseModel):
    results: list[dict]
    total: int
