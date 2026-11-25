from typing import Dict, Any
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, AIMessage
from flashrank import Ranker, RerankRequest

from app.schema.state import State
from app.config.llm import llm
from app.Ingestion_Pipeline.ingestion import db

# Initialize FlashRank once at module level
ranker = Ranker(model_name="ms-marco-MiniLM-L-12-v2")


# Optional: Tool wrapper if you bind tools to an LLM agent later
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

    prompt = ChatPromptTemplate.from_messages([
        (
            "system",
            "Rewrite the user's latest question into a standalone search query using the chat history. "
            "Do not answer the question—only return the improved query."
        ),
        ("placeholder", "{history}"),
        ("human", "{question}"),
    ])

    try:
        chain = prompt | llm
        response = chain.invoke({"history": history[:-1], "question": question})
        return {"rewritten_question": response.content.strip(), "error": None}
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
            "error": None if docs else "No documents found.",
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
        return {"context": "", "citations": [], "error": "No documents to rerank."}

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
        return {"error": f"Reranking failed: {e}"}


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
        }

    prompt = ChatPromptTemplate.from_messages([
        (
            "system",
            """You are a helpful RAG assistant.
                Answer the user's question using ONLY the provided context.
                If the answer is not available in the context, clearly say that you don't have enough information.

                IMPORTANT:
                - Add inline citations for factual claims using [1], [2], etc.
                - Only cite sources provided in the context.
                - Do not invent citations.

                Context:
                {context}"""
                        ),
                        ("human", "{question}"),
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