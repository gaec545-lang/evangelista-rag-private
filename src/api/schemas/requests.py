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


class ProjectContext(BaseModel):
    sector: str | None = None
    hypotheses_count: int | None = 0
    findings_summary: list[str] | None = Field(default_factory=list)
    current_coi: float | None = 0.0


class TabContext(BaseModel):
    model_config = {"extra": "allow"}


class ClientContext(BaseModel):
    model_config = {"extra": "allow"}


class ProjectContextFull(BaseModel):
    model_config = {"extra": "allow"}


from typing import Literal

class ChatRequest(BaseModel):
    message: str
    agent_name: str
    project_phase: str | None = "scoping"
    project_context: ProjectContext | None = None
    eva_mode: Literal['global', 'client', 'project'] = 'global'
    tab_context: TabContext | None = None
    client_context: ClientContext | None = None
    project_context_full: ProjectContextFull | None = None


class ChatResponse(BaseModel):
    message: str
    agent_used: str
    rag_status: str = "OK"
    avg_relevance: float = 0.0
    retriever_used: str = ""
    hypothesis_used: bool = False
