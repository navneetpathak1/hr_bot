import os
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from langchain_community.document_loaders import TextLoader, PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_postgres import PGVector

from app.config.embedding import embeddings

load_dotenv()

CONNECTION_STRING = os.getenv("CONNECTION_STRING")
COLLECTION_NAME = os.getenv("COLLECTION_NAME")

if not CONNECTION_STRING:
    raise ValueError("CONNECTION_STRING is missing from .env")

engine = create_engine(CONNECTION_STRING)

db = PGVector(
    embeddings=embeddings,
    collection_name=COLLECTION_NAME,
    connection=CONNECTION_STRING,
)


def init_db() -> None:
    """Create tracking table for ingested files."""
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS processed_files (
                id SERIAL PRIMARY KEY,
                file_name VARCHAR(255) UNIQUE NOT NULL
            )
        """))

BASE_DIR = Path(__file__).resolve().parents[2]
DATA_FOLDER = BASE_DIR / "data"

def ingest_files(data_folder: Path = DATA_FOLDER, vector_store: PGVector = db) -> None:
    """Load, chunk, and store new PDF/TXT files into PGVector."""
    if not data_folder.exists():
        raise FileNotFoundError(f"Folder not found: {data_folder}")

    init_db()

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=80,
    )

    for file_path in data_folder.iterdir():
        if file_path.suffix.lower() not in [".pdf", ".txt"]:
            continue

        with engine.connect() as conn:
            exists = conn.execute(
                text("SELECT EXISTS (SELECT 1 FROM processed_files WHERE file_name = :file_name)"),
                {"file_name": file_path.name},
            ).scalar()

        if exists:
            print(f"Already processed: {file_path.name}")
            continue

        try:
            loader = (
                PyPDFLoader(str(file_path))
                if file_path.suffix.lower() == ".pdf"
                else TextLoader(str(file_path), encoding="utf-8")
            )
            documents = loader.load()

            for doc in documents:
                doc.metadata["source"] = file_path.name

            chunks = text_splitter.split_documents(documents)
            if not chunks:
                print(f"No content found: {file_path.name}")
                continue

            vector_store.add_documents(documents=chunks)

            with engine.begin() as conn:
                conn.execute(
                    text("INSERT INTO processed_files (file_name) VALUES (:file_name)"),
                    {"file_name": file_path.name},
                )

            print(f"Successfully stored: {file_path.name} ({len(chunks)} chunks)")

        except Exception as e:
            print(f"Failed to process {file_path.name}: {e}")