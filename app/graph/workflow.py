from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from app.schema.state import State
from app.graph.nodes import (
    rewrite_query_node,
    retrieve_node,
    rerank_node,
    generate_answer_node,
)

MAX_RETRIES = 2


def route_after_retrieve(state: State) -> str:
    """Retry retrieval on transient failure, otherwise proceed to rerank or generate."""
    if state.get("error") and state.get("retry_count", 0) < MAX_RETRIES:
        return "retry"
    if not state.get("retrieved_documents"):
        return "generate"
    return "rerank"


def build_rag_graph(checkpointer=None):
    workflow = StateGraph(State)

    # Register nodes
    workflow.add_node("rewrite_query", rewrite_query_node)
    workflow.add_node("retrieve", retrieve_node)
    workflow.add_node("rerank", rerank_node)
    workflow.add_node("generate", generate_answer_node)

    # Define edges
    workflow.add_edge(START, "rewrite_query")
    workflow.add_edge("rewrite_query", "retrieve")

    workflow.add_conditional_edges(
        "retrieve",
        route_after_retrieve,
        {
            "retry": "retrieve",
            "rerank": "rerank",
            "generate": "generate",
        },
    )

    workflow.add_edge("rerank", "generate")
    workflow.add_edge("generate", END)

    # Attach checkpointer for conversation persistence
    if checkpointer is None:
        checkpointer = MemorySaver()
    return workflow.compile(checkpointer=checkpointer)


# Shared singleton for persistent conversation memory
memory = MemorySaver()
rag_app = build_rag_graph(checkpointer=memory)


