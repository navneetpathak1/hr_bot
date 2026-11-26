from fastapi import APIRouter, Depends, HTTPException, status
from typing import Annotated
from langchain_core.messages import HumanMessage

from .user_route import get_current_user
from app.models.user_models import User
from app.graph.workflow import rag_app
from app.PII.imports_PII import extract_pii

router = APIRouter()

# Define the query endpoint and handle the RAG processing and PII detection

@router.get("/query")
async def query_endpoint(
    query: str,
    current_user: Annotated[User, Depends(get_current_user)]
):
    if not query.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Query cannot be empty"
        )

    pii_result = extract_pii(query)

    if pii_result:
        return {
            "question": query,
            "rewritten_question": None,
            "answer": (
                "Sensitive information detected. "
                "Please remove sensitive information and try again."
            ),
            "citations": []
        }


    thread_id = f"user_{current_user.id}"
    config = {"configurable": {"thread_id": thread_id}}

    initial_input = {
        "question": query,
        "messages": [HumanMessage(content=query)],
        "retry_count": 0,
        "error": None,
    }

    try:
        result = rag_app.invoke(initial_input, config=config)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"RAG processing failed: {e}"
        )

    return {
        "question": result.get("question"),
        "rewritten_question": result.get("rewritten_question"),
        "answer": result.get("answer"),
        "citations": result.get("citations", [])
    }
