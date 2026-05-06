from src.graph.state import GraphState

def decide_after_quality(state: GraphState) -> str:
    """Post-quality check: pasa a synthesizer o re-genera."""
    if state.quality_check:
        return "synthesizer"
    elif state.retry_count < state.max_retries:
        return "generator"
    return "synthesizer"
