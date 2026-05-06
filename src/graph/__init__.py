"""
src.graph — Advanced RAG con LangGraph, CRAG y Self-Reflective RAG.

Arquitectura:
    Router → Retriever → Grader → Generator → Hallucination Check → Quality Check → END
                ↓ (no relevant)      ↑ (re-retrieve)
           Web Searcher ──────────────
                ↓ (tool route)
           Tool Executor ─────────────→ Synthesizer → END
"""
from .builder import build_graph, run_graph
from .state import GraphState, RetrievedDocument, NodeStatus

__all__ = ["build_graph", "run_graph", "GraphState", "RetrievedDocument", "NodeStatus"]
