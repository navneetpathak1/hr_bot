import os
from langchain_groq import ChatGroq
from dotenv import load_dotenv
load_dotenv

API_KEY = os.getenv("GROQ_API_KEY")
llm = ChatGroq(
    model="qwen/qwen3-32b",
    temperature=0.3,
    api_key= API_KEY
)