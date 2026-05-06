from src.graph.state import GraphState

def decide_after_hallucination(state: GraphState) -> str:
    """Post-hallucination check: pasa a quality o re-genera."""
    if state.hallucination_check:
        return "quality_check"
    elif state.retry_count < state.max_retries:
        return "generator"
    return "synthesizer"
