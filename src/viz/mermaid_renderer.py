"""
Renderizador de diagramas Mermaid.js para el grafo Advanced RAG.

Dos modos:
  1. render_graph_definition() — diagrama estático de la arquitectura completa
  2. render_execution_trace(state) — recorrido real de una ejecución específica
"""
from __future__ import annotations

# Importación lazy para evitar circular imports
_GRAPH_STATE_TYPE = None


def _get_state_type():
    global _GRAPH_STATE_TYPE
    if _GRAPH_STATE_TYPE is None:
        from src.graph.state import GraphState  # noqa: PLC0415
        _GRAPH_STATE_TYPE = GraphState
    return _GRAPH_STATE_TYPE


# Mapa de nombre interno → etiqueta legible en el diagrama
_NODE_LABELS: dict[str, str] = {
    "router":             "Router",
    "retriever":          "Retriever",
    "grader":             "CRAG Grader",
    "web_searcher":       "Web Searcher",
    "tool_executor":      "Tool Executor",
    "generator":          "Generator",
    "hallucination_check": "Hallucination Check",
    "quality_check":      "Quality Check",
    "synthesizer":        "Synthesizer",
}


def render_graph_definition() -> str:
    """Diagrama Mermaid estático — arquitectura completa del grafo Advanced RAG."""
    return """\
stateDiagram-v2
    [*] --> Router

    Router --> Retriever : rag / multi
    Router --> ToolExecutor : tools
    Router --> WebSearcher : web

    Retriever --> CRAGGrader

    CRAGGrader --> Generator : relevant (≥30%)
    CRAGGrader --> WebSearcher : not relevant (0%)
    CRAGGrader --> Retriever : refine query (<30%)

    WebSearcher --> Generator
    ToolExecutor : Tool Executor
    ToolExecutor --> Generator

    Generator --> HallucinationCheck
    HallucinationCheck : Hallucination Check
    HallucinationCheck --> QualityCheck : grounded ✓
    HallucinationCheck --> Generator : hallucinated ↺ (retry)
    HallucinationCheck --> Synthesizer : max retries

    QualityCheck : Quality Check
    QualityCheck --> Synthesizer : useful ✓
    QualityCheck --> Retriever : not useful ↺ (retry)

    Synthesizer --> [*]

    note right of CRAGGrader
        Corrective RAG
        Evalúa relevancia chunk a chunk
        Ratio < 30%% → web search
    end note

    note right of HallucinationCheck
        Self-Reflective RAG
        ¿La respuesta está fundamentada
        en las fuentes?
    end note

    note right of QualityCheck
        Self-Reflective RAG
        ¿La respuesta contesta
        la pregunta original?
    end note"""


def render_execution_trace(state: "GraphState") -> str:  # type: ignore[name-defined]
    """
    Diagrama Mermaid que muestra el recorrido REAL de una ejecución.
    Usa el node_history y mermaid_log del GraphState.
    """
    lines = ["stateDiagram-v2"]
    history = state.node_history

    if not history:
        return "stateDiagram-v2\n    [*] --> Sin_datos\n    Sin_datos --> [*]"

    def _label(key: str) -> str:
        """Convierte clave interna a etiqueta Mermaid segura (sin espacios)."""
        return (_NODE_LABELS.get(key) or key).replace(" ", "_")

    # Entrada al primer nodo
    lines.append(f"    [*] --> {_label(history[0])}")

    # Transiciones según el recorrido real
    seen_transitions: set[str] = set()
    for i in range(len(history) - 1):
        src = _label(history[i])
        dst = _label(history[i + 1])

        # Detectar ciclos (re-intentos)
        is_retry = i > 0 and history[i + 1] in history[:i]
        suffix = " : retry" if is_retry else ""
        transition = f"    {src} --> {dst}{suffix}"

        if transition not in seen_transitions:
            lines.append(transition)
            seen_transitions.add(transition)

    # Nodo final → END
    lines.append(f"    {_label(history[-1])} --> [*]")

    # Notas con detalles de cada nodo (desde mermaid_log)
    for entry in state.mermaid_log:
        node_key: str = entry.get("node") or ""
        detail: str = entry.get("detail") or ""
        if node_key and detail:
            safe_label = _label(node_key)
            # Limpiar caracteres no soportados por Mermaid en notas
            safe_detail = detail.replace("→", "->").replace("↺", "retry")
            lines.append(f"    note right of {safe_label}")
            lines.append(f"        {safe_detail}")
            lines.append(f"    end note")

    return "\n".join(lines)
