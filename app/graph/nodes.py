from typing import Dict, Any
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, AIMessage
from flashrank import Ranker, RerankRequest

from app.schema.state import State
from app.config.llm import llm
from app.Ingestion_Pipeline.ingestion import db
from app.prompt.prompt import HR_PROMPT
# Initialize FlashRank once at module level
ranker = Ranker(model_name="ms-marco-MiniLM-L-12-v2")

@tool
def search_knowledge_base(query: str) -> str:
    """Search and rerank documents from the vector database for a given query."""
    docs = db.similarity_search(query=query, k=8)
    passages = [
        {"id": str(i), "text": d.page_content, "meta": d.metadata}
        for i, d in enumerate(docs)
    ]
    ranked = ranker.rerank(RerankRequest(query=query, passages=passages))[:4]
    return "\n\n".join(docs[int(r["id"])].page_content for r in ranked)


def rewrite_query_node(state: State) -> Dict[str, Any]:
    """Rewrite the user question using conversation history for standalone retrieval."""
    question = state["question"]
    history = state.get("messages", [])

    # Skip rewriting if there is no prior conversation history
    if len(history) <= 1:
        return {"rewritten_question": question, "error": None}

    history_text = "\n".join(
        f"{'User' if isinstance(m, HumanMessage) else 'Assistant'}: {m.content}"
        for m in history[:-1]
    )

    prompt = ChatPromptTemplate.from_messages([
        (
            "system",
            "You are a query rewriting assistant. Given a chat history and the user's latest follow-up question, "
            "rewrite the question into a single, concise standalone search query for document retrieval. "
            "Do not answer the question. Return ONLY the rewritten query without quotes or preamble."
        ),
        (
            "human",
            f"Chat History:\n{history_text}\n\nFollow-up question: {question}\n\nStandalone search query:"
        ),
    ])

    try:
        chain = prompt | llm
        response = chain.invoke({})
        rewritten = response.content.strip()
        return {"rewritten_question": rewritten if rewritten else question, "error": None}
    except Exception as e:
        return {"rewritten_question": question, "error": str(e)}


def retrieve_node(state: State) -> Dict[str, Any]:
    """Retrieve candidate documents from PGVector."""
    query = state.get("rewritten_question") or state["question"]
    retries = state.get("retry_count", 0)

    try:
        docs = db.similarity_search(query=query, k=10)
        return {
            "retrieved_documents": docs,
            "error": None,
        }
    except Exception as e:
        return {
            "retrieved_documents": [],
            "retry_count": retries + 1,
            "error": f"Retrieval failed: {e}",
        }


def rerank_node(state: State) -> Dict[str, Any]:
    """Rerank retrieved documents using FlashRank and format context with citations."""
    query = state.get("rewritten_question") or state["question"]
    retrieved_docs = state.get("retrieved_documents", [])

    if not retrieved_docs:
        return {"context": "", "citations": [], "error": None}

    try:
        passages = [
            {"id": str(i), "text": doc.page_content, "meta": doc.metadata}
            for i, doc in enumerate(retrieved_docs)
        ]

        reranked_results = ranker.rerank(RerankRequest(query=query, passages=passages))
        top_results = reranked_results[:4]

        context_parts = []
        citations = []
        top_docs = []

        for idx, result in enumerate(top_results, start=1):
            doc = retrieved_docs[int(result["id"])]
            top_docs.append(doc)

            source = doc.metadata.get("source", "Unknown source")
            page = doc.metadata.get("page", "N/A")
            citation = f"[{idx}] Source: {source}, Page: {page}"

            context_parts.append(f"{doc.page_content}\nCitation: {citation}")
            citations.append(citation)

        return {
            "retrieved_documents": top_docs,
            "context": "\n\n".join(context_parts),
            "citations": citations,
            "error": None,
        }
    except Exception as e:
        top_docs = retrieved_docs[:4]
        context_parts = []
        citations = []
        for idx, doc in enumerate(top_docs, start=1):
            source = doc.metadata.get("source", "Unknown source")
            page = doc.metadata.get("page", "N/A")
            citation = f"[{idx}] Source: {source}, Page: {page}"
            context_parts.append(f"{doc.page_content}\nCitation: {citation}")
            citations.append(citation)

        return {
            "retrieved_documents": top_docs,
            "context": "\n\n".join(context_parts),
            "citations": citations,
            "error": f"Reranking failed: {e}",
        }


def generate_answer_node(state: State) -> Dict[str, Any]:
    """Generate a grounded answer with inline citations."""
    question = state["question"]
    context = state.get("context", "")
    retries = state.get("retry_count", 0)

    if not context:
        fallback = "I don't have enough information in the provided documents to answer that."
        return {
            "answer": fallback,
            "messages": [AIMessage(content=fallback)],
            "error": None,
        }

    prompt = ChatPromptTemplate.from_messages([
        ("system", HR_PROMPT),
        (
            "human",
            "<COMPANY_POLICY_CONTEXT>\n"
            "{context}\n"
            "</COMPANY_POLICY_CONTEXT>\n\n"
            "<EMPLOYEE_QUESTION>\n"
            "{question}\n"
            "</EMPLOYEE_QUESTION>\n\n"
            "Answer:"
        ),
    ])

    try:
        chain = prompt | llm
        response = chain.invoke({"context": context, "question": question})
        answer_text = response.content

        return {
            "answer": answer_text,
            "messages": [AIMessage(content=answer_text)],
            "error": None,
        }
    except Exception as e:
        return {
            "retry_count": retries + 1,
            "error": f"Generation failed: {e}",
        }
