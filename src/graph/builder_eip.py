"""
Builder del grafo de Debate Multi-Agente EIP.

Arquitectura corregida del StateGraph:
    START → eip_router ──(distribuir)──┐
                                       ├→ financial_node ─┐
                                       ├→ process_node ──┤
                                       └→ data_engineer_node ┘

    Cada agente consulta herramientas PERIFÉRICAS:
        financial_node ↔ rag_node     (ida/vuelta)
        financial_node ↔ sandbox_node (ida/vuelta)
        process_node   ↔ rag_node     (ida/vuelta)
        process_node   ↔ sandbox_node (ida/vuelta)
        data_eng_node  ↔ rag_node     (ida/vuelta)
        data_eng_node  ↔ sandbox_node (ida/vuelta)

    Debate cruzado:
        process_node ──(fricción)──→ financial_node
        data_eng_node ──(viabilidad)──→ financial_node

    Convergencia:
        financial_node ──→ consensus ──→ grader
        (si grader rechaza → financial_node, NO consensus)
        (si grader aprueba → eip_synthesizer ──→ END)
"""
from __future__ import annotations

import time
from langgraph.graph import StateGraph, END
from .state import GraphState
import structlog

logger = structlog.get_logger(__name__)

# ─── Nodos ────────────────────────────────────────────────────────────────────
from .nodes.eip_router import eip_router
from .nodes.agent_nodes import financial_node, process_node, data_engineer_node
from .nodes.consensus import consensus_node
from .nodes.eip_grader import eip_grader
from .nodes.eip_synthesizer import eip_synthesizer
from .nodes.tool_nodes import rag_node, sandbox_node

# ─── Aristas condicionales ────────────────────────────────────────────────────
from .edges.eip_distribute import distribute_swarm
from .edges.eip_grader_decision import decide_after_eip_grader


def build_eip_graph() -> StateGraph:
    """Construye y compila el grafo de Debate Multi-Agente EIP."""
    workflow = StateGraph(GraphState)

    # ── Nodos ──────────────────────────────────────────────────────────────
    workflow.add_node("eip_router", eip_router)
    workflow.add_node("financial_node", financial_node)
    workflow.add_node("process_node", process_node)
    workflow.add_node("data_engineer_node", data_engineer_node)
    workflow.add_node("rag_node", rag_node)
    workflow.add_node("sandbox_node", sandbox_node)
    workflow.add_node("consensus", consensus_node)
    workflow.add_node("eip_grader", eip_grader)
    workflow.add_node("eip_synthesizer", eip_synthesizer)

    # ── Entry point ────────────────────────────────────────────────────────
    workflow.set_entry_point("eip_router")

    # ── Router → distribuir al enjambre ─────────────────────────────────────
    workflow.add_conditional_edges(
        "eip_router",
        distribute_swarm,
        {
            "financial_node": "financial_node",
            "process_node": "process_node",
            "data_engineer_node": "data_engineer_node",
        },
    )

    # ═══════════════════════════════════════════════════════════════════════
    # CORRECCIÓN 1: Tool Calling — cada agente puede consultar herramientas
    # ═══════════════════════════════════════════════════════════════════════
    # Los agentes tienen un edge condicional que decide si:
    #   - Consultar RAG  → rag_node (que regresa incondicionalmente al agente)
    #   - Consultar Sandbox → sandbox_node (que regresa incondicionalmente al agente)
    #   - Ir al consenso (cuando ya no necesita herramientas)

    def financial_tool_route(state: GraphState) -> str:
        """Financial Agent → RAG / Sandbox / Consenso."""
        # TODO: lógica real de decisión basada en el estado
        return "consensus"

    def process_tool_route(state: GraphState) -> str:
        """Process Agent → RAG / Sandbox / Financial o Consenso."""
        return "consensus"

    def data_eng_tool_route(state: GraphState) -> str:
        """DataEng Agent → RAG / Sandbox / Financial o Consenso."""
        return "consensus"

    # ── Financial Agent ── conditional a herramientas o consenso ──────────
    workflow.add_conditional_edges(
        "financial_node",
        financial_tool_route,
        {
            "rag_node": "rag_node",
            "sandbox_node": "sandbox_node",
            "consensus": "consensus",
        },
    )

    # ── Process Agent ── conditional a herramientas, fricción o consenso ──
    workflow.add_conditional_edges(
        "process_node",
        process_tool_route,
        {
            "rag_node": "rag_node",
            "sandbox_node": "sandbox_node",
            "financial_node": "financial_node",
            "consensus": "consensus",
        },
    )

    # ── DataEng Agent ── conditional a herramientas, viabilidad o consenso ─
    workflow.add_conditional_edges(
        "data_engineer_node",
        data_eng_tool_route,
        {
            "rag_node": "rag_node",
            "sandbox_node": "sandbox_node",
            "financial_node": "financial_node",
            "consensus": "consensus",
        },
    )

    # ═══════════════════════════════════════════════════════════════════════
    # CORRECCIÓN 2: Tool Nodes → regresan incondicionalmente al agente
    # ═══════════════════════════════════════════════════════════════════════
    # Las herramientas son periféricas: terminan y devuelven el control
    # al agente que las invocó. Se usa send() de LangGraph para retornar
    # al nodo del caller basado en current_agent.

    def route_from_rag(state: GraphState) -> str:
        """RAG Node → regresa al agente que lo invocó."""
        caller = state.current_agent
        if caller == "process":
            return "process_node"
        elif caller == "data_engineer":
            return "data_engineer_node"
        return "financial_node"  # default

    def route_from_sandbox(state: GraphState) -> str:
        """Sandbox Node → regresa al agente que lo invocó."""
        caller = state.current_agent
        if caller == "process":
            return "process_node"
        elif caller == "data_engineer":
            return "data_engineer_node"
        return "financial_node"  # default

    # ── RAG Node → condicional de vuelta al caller ────────────────────────
    workflow.add_conditional_edges(
        "rag_node",
        route_from_rag,
        {
            "financial_node": "financial_node",
            "process_node": "process_node",
            "data_engineer_node": "data_engineer_node",
        },
    )

    # ── Sandbox Node → condicional de vuelta al caller ────────────────────
    workflow.add_conditional_edges(
        "sandbox_node",
        route_from_sandbox,
        {
            "financial_node": "financial_node",
            "process_node": "process_node",
            "data_engineer_node": "data_engineer_node",
        },
    )

    # ═══════════════════════════════════════════════════════════════════════
    # Consenso → Grader (flujo unidireccional)
    # ═══════════════════════════════════════════════════════════════════════
    workflow.add_edge("consensus", "eip_grader")

    # ═══════════════════════════════════════════════════════════════════════
    # Grader → rechaza (vuelta al ENJAMBRE) o aprueba (synth)
    # ═══════════════════════════════════════════════════════════════════════
    # CORRECCIÓN: rechazo VA al enjambre (financial_node), NO a consensus
    workflow.add_conditional_edges(
        "eip_grader",
        decide_after_eip_grader,
        {
            "financial_node": "financial_node",      # rechazo: regenerar
            "eip_synthesizer": "eip_synthesizer",     # aprobado
        },
    )

    # ── Synthesizer → END ──────────────────────────────────────────────────
    workflow.add_edge("eip_synthesizer", END)

    return workflow.compile()


# ─── Alias para backward compat ────────────────────────────────────────────────
create_eip_graph = build_eip_graph


async def run_eip_graph(
    scqa_input: dict,
    context: dict | None = None,
    thread_id: str = "eip-default",
) -> GraphState:
    """Punto de entrada del grafo EIP Multi-Agente."""
    logger.info("eip_graph_start", scqa=scqa_input, thread_id=thread_id)
    start = time.time()

    compiled = build_eip_graph()
    initial_state = GraphState(
        scqa_input=scqa_input,
        context=context or {},
        thread_id=thread_id,
    )

    raw = await compiled.ainvoke(initial_state)
    final: GraphState = GraphState(**raw) if isinstance(raw, dict) else raw  # type: ignore[assignment]

    elapsed = int((time.time() - start) * 1000)
    object.__setattr__(final, "execution_time_ms", elapsed)

    logger.info(
        "eip_graph_complete",
        consensus=final.swarm_consensus,
        nodes=len(final.node_history),
        time_ms=elapsed,
    )
    return final
