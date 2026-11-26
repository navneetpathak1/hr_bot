from typing import TypedDict, List, Optional, Any, Annotated
from langgraph.graph.message import add_messages


class State(TypedDict):
    question: str
    rewritten_question: Optional[str]
    retrieved_documents: List[Any]
    context: str
    answer: str
    citations: List[str]
    retry_count: int
    error: Optional[str]
    messages: Annotated[list, add_messages]