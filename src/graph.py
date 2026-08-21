"""
graph.py
--------
The LangGraph pipeline wiring it all together.

State Flow:
1. Extraction Node -> `ExtractedClaim`
2. Validation Node -> `ValidationResult` (and Decision)
3. Summarization Node (Conditional) -> `caseworker_summary`

The graph takes in the `ClaimRegistry` so that duplicate state is preserved
across multiple claim runs in the same batch.
"""

from langgraph.graph import StateGraph, END

from models import AgentState
from extraction import run_extraction
from validation import make_validation_node
from summarization import run_summarization
from registry import ClaimRegistry


def should_summarize(state: AgentState) -> str:
    """Conditional edge logic."""
    if state.extraction_error:
        return "summarize"  # Extraction failed -> always escalate/summarize
    if state.final_decision and state.final_decision.value == "ESCALATE":
        return "summarize"
    return "end"


def build_adjudication_graph(registry: ClaimRegistry):
    """Build and compile the LangGraph workflow."""
    
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("extract", run_extraction)
    workflow.add_node("validate", make_validation_node(registry))
    workflow.add_node("summarize", run_summarization)

    # Define the flow
    workflow.set_entry_point("extract")
    
    # If extraction fails, the validation node will catch it and skip itself,
    # but let's route it normally so validation can just NOOP.
    workflow.add_edge("extract", "validate")
    
    # Conditional routing after validation
    workflow.add_conditional_edges(
        "validate",
        should_summarize,
        {
            "summarize": "summarize",
            "end": END,
        }
    )
    
    workflow.add_edge("summarize", END)

    return workflow.compile()
