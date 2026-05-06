"""
Nodo Tool Executor: Ejecuta herramientas externas (cálculos, SQL).
"""
from ..state import GraphState
from ..tools.calculator import PricingCalculator
import structlog

logger = structlog.get_logger()

async def execute_tools(state: GraphState) -> GraphState:
    """Ejecuta herramientas de cálculo cuando el router decide 'tools'."""
    calculator = PricingCalculator()
    tool_results = {}
    
    # Detectar qué cálculos se piden basándose en keywords
    q = state.question.lower()
    
    if any(kw in q for kw in ["gamma", "γ", "factor g", "setup fee", "sucursales", "cuanto cuesta", "precio"]):
        result = calculator.estimate_from_text(state.question)
        tool_results["pricing_calculator"] = result
    
    if any(kw in q for kw in ["roi", "retorno", "inversión"]):
        result = calculator.estimate_roi(state.question)
        tool_results["roi_calculator"] = result
    
    if any(kw in q for kw in ["alpha", "α", "volumen", "registros"]):
        result = calculator.calculate_alpha_from_text(state.question)
        tool_results["alpha_calculator"] = result
    
    if not tool_results:
        tool_results["default"] = "No se detectaron cálculos específicos. Procesando con RAG."
    
    logger.info("tool_execution", tools_used=list(tool_results.keys()))
    
    return state.model_copy(update={
        "tool_results": tool_results,
        "current_node": "tool_executor",
        "node_history": state.node_history + ["tool_executor"],
        "mermaid_log": state.mermaid_log + [{"node": "tool_executor", "status": "completed", "detail": ", ".join(tool_results.keys())}]
    })
