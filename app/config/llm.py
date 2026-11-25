import os
from langchain_groq import ChatGroq
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("GROQ_API_KEY")
MODEL_NAME = os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b")

llm = ChatGroq(
    model=MODEL_NAME,
    temperature=0.3,
    api_key=API_KEY
)