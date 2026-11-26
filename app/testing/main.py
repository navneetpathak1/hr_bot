from langchain_core.messages import HumanMessage

from app.Ingestion_Pipeline.ingestion import ingest_files, db
from app.graph.workflow import rag_app

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]

DATA_FOLDER = BASE_DIR / "data"

def ask_question(graph, question: str, thread_id: str = "user-session-1"):
    config = {"configurable": {"thread_id": thread_id}}

    initial_input = {
        "question": question,
        "messages": [HumanMessage(content=question)],
        "retry_count": 0,
        "error": None,
    }

    result = graph.invoke(initial_input, config=config)

    print(f"\nQuestion: {result['question']}")
    if result.get("rewritten_question") and result.get("rewritten_question") != result["question"]:
        print(f"Rewritten Query: {result['rewritten_question']}")
    print(f"Answer:\n{result.get('answer', '')}")
    print("\nSources:")
    citations = result.get("citations", [])
    for citation in citations:
        print(f"  {citation}")

    return [result, citations]


if __name__ == "__main__":
    print("Starting file ingestion...")
    ingest_files(DATA_FOLDER, db)
    print("File ingestion completed!\n")


    # Turn 1
    ask_question(rag_app, "What is the main topic of the documents?", thread_id="session_1")

    # Turn 2 (MemorySaver retains context from Turn 1 so 'it' gets rewritten properly)
    ask_question(rag_app, "Can you summarize the key points about it?", thread_id="session_1")


# uv run python -m app.testing.main

