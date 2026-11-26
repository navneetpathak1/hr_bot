# HR-RAG 🤖

An intelligent **HR Policy Q&A system** powered by Retrieval-Augmented Generation (RAG). Employees can ask natural-language questions about company policies and receive accurate, cited answers grounded exclusively in uploaded HR documents — with built-in PII detection, JWT authentication, and conversation memory.

---

## ✨ Features

| Feature | Description |
|---|---|
| 🔍 **Semantic Search** | Retrieves relevant policy chunks from a PGVector database using sentence-transformer embeddings |
| 🏆 **Neural Re-ranking** | Re-ranks retrieved chunks with FlashRank (`ms-marco-MiniLM-L-12-v2`) for precision |
| 🔄 **Query Rewriting** | Rewrites follow-up questions into standalone queries using conversation history |
| 💬 **Conversational Memory** | Per-user thread memory via LangGraph's `MemorySaver` |
| 📄 **Inline Citations** | Every answer references the source document and page number |
| 🛡️ **PII Detection** | Blocks queries containing sensitive personal information before they hit the LLM |
| 🔐 **JWT Authentication** | Secure register/login with Argon2-hashed passwords and JWT bearer tokens |
| 🗄️ **Alembic Migrations** | Schema-managed PostgreSQL database with async SQLAlchemy |
| 🖥️ **MCP Server** | Model Context Protocol server exposing HR prompts as reusable tools |
| ⚡ **React Frontend** | Vite + React 19 SPA with Login, Register, and Chat pages |

---

## 🏗️ Architecture

```
                    ┌──────────────────┐
                    │   React Frontend │  (Vite + React 19)
                    │  Login / Chat UI │
                    └────────┬─────────┘
                             │ HTTP (JWT Bearer)
                    ┌────────▼─────────┐
                    │   FastAPI Backend │
                    │  /api/v1/query   │
                    │  /api/v1/login   │
                    │  /api/v1/register│
                    └────────┬─────────┘
                             │
              ┌──────────────▼──────────────┐
              │        LangGraph RAG         │
              │                             │
              │  rewrite_query              │
              │       │                     │
              │  retrieve (PGVector)        │
              │       │                     │
              │  rerank (FlashRank)         │
              │       │                     │
              │  generate (Groq LLM)        │
              └──────────────┬──────────────┘
                             │
              ┌──────────────▼──────────────┐
              │  PostgreSQL + pgvector       │
              │  (Documents + User records) │
              └─────────────────────────────┘
```

### RAG Pipeline Nodes

```
START → rewrite_query → retrieve ──(success)──► rerank → generate → END
                              └──(error/retry)──► retrieve (up to 2 retries)
                              └──(no docs)──────► generate → END
```

---

## 🗂️ Project Structure

```
HR_RAG/
├── app/
│   ├── config/
│   │   ├── database.py         # Async SQLAlchemy engine & session
│   │   ├── embedding.py        # HuggingFace sentence-transformer embeddings
│   │   └── llm.py              # Groq ChatGroq LLM setup
│   ├── graph/
│   │   ├── nodes.py            # LangGraph nodes: rewrite, retrieve, rerank, generate
│   │   └── workflow.py         # StateGraph definition and compiled RAG app
│   ├── Ingestion_Pipeline/
│   │   └── ingestion.py        # PDF/TXT loader → chunker → PGVector ingestor
│   ├── models/
│   │   └── user_models.py      # SQLAlchemy User model
│   ├── PII/
│   │   └── imports_PII.py      # PII extraction & redaction (cbx-indic-pii-extractor-17M)
│   ├── prompt/
│   │   └── prompt.py           # HR_PROMPT and REWRITE_PROMPT templates
│   ├── routes/
│   │   ├── main_route.py       # FastAPI app, CORS, exception handlers
│   │   ├── query_route.py      # /query endpoint with PII guard & RAG invocation
│   │   └── user_route.py       # /register, /login, /profile endpoints
│   └── schema/
│       ├── state.py            # LangGraph State TypedDict
│       └── user_schema.py      # Pydantic schemas for auth
├── frontend/                   # Vite + React 19 SPA
│   └── src/
│       ├── pages/
│       │   ├── Login.jsx
│       │   ├── Register.jsx
│       │   └── Chat.jsx
│       └── api.js              # Axios/fetch API helpers
├── alembic/                    # Database migration scripts
├── EVALS/                      # DeepEval RAG evaluation suite
│   ├── eval_rag.py
│   ├── eval_results.json
│   └── groq_deepeval_model.py
├── MCP_/                       # Model Context Protocol server
│   ├── server.py               # MCP server exposing HR prompts
│   └── client.py
├── models/                     # Local ML models (PII extractor)
│   └── cbx-indic-pii-extractor-17M/
├── data/                       # HR policy documents (PDF/TXT) for ingestion
├── Tests/                      # pytest test suite
├── pyproject.toml
└── .env
```

---

## 🚀 Getting Started

### Prerequisites

- **Python ≥ 3.11** (managed via `uv`)
- **Node.js ≥ 18** (for the frontend)
- **PostgreSQL** with the [`pgvector`](https://github.com/pgvector/pgvector) extension enabled
- A **[Groq](https://console.groq.com/)** API key

### 1. Clone & Install

```bash
git clone <repo-url>
cd HR_RAG

# Install Python dependencies with uv
uv sync
```

### 2. Configure Environment Variables

Create a `.env` file in the project root:

```env
# Database
CONNECTION_STRING=postgresql://user:password@localhost:5432/hr_rag
COLLECTION_NAME=hr_policies

# LLM
GROQ_API_KEY=your_groq_api_key
GROQ_MODEL=qwen/qwen3.8-27b          # optional, this is the default

# Auth
JWT_SECRET=your_super_secret_key
JWT_ALGO=HS256
```

### 3. Set Up the Database

```bash
# Apply Alembic migrations to create user tables
uv run alembic upgrade head
```

### 4. Ingest HR Documents

Place your PDF or TXT policy files inside the `data/` folder, then run:

```bash
uv run python -c "from app.Ingestion_Pipeline.ingestion import ingest_files; ingest_files()"
```

This will:
- Chunk documents into 500-token segments (80-token overlap)
- Embed them with `sentence-transformers/all-MiniLM-L6-v2`
- Store vectors in PGVector
- Track processed files to avoid re-ingestion

### 5. Start the Backend

```bash
uv run fastapi dev app/routes/main_route.py
```

The API will be available at `http://localhost:8000`.  
Interactive docs: `http://localhost:8000/docs`

### 6. Start the Frontend

```bash
cd frontend
npm install
npm run dev
```

The UI will be available at `http://localhost:5173`.

---

## 🔌 API Reference

### Authentication

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/register` | Register a new user (returns JWT) |
| `POST` | `/api/v1/login` | Login with username/email + password (returns JWT) |
| `GET` | `/api/v1/profile` | Get current user profile (requires JWT) |

### Query

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/v1/query?query=<text>` | Ask an HR policy question (requires JWT) |

**Example response:**
```json
{
  "question": "How many sick days do I get?",
  "rewritten_question": "sick leave entitlement per year",
  "answer": "Employees are entitled to 10 paid sick days per year [1]...",
  "citations": ["[1] Source: hr_policy_2024.pdf, Page: 12"]
}
```

> **PII Guard:** If the query contains personal identifiable information (names, Aadhaar, phone numbers, etc.), the endpoint returns a safe refusal message without invoking the LLM.

---

## 🧪 Evaluation

The project includes a [`DeepEval`](https://github.com/confident-ai/deepeval) evaluation suite in `EVALS/`:

```bash
uv run python -m EVALS.eval_rag
```

Metrics evaluated:
- **Faithfulness** – Is the answer grounded in the retrieved context?
- **Answer Relevancy** – Does the answer address the question?
- **Contextual Precision / Recall** – Quality of retrieval

Results are saved to `EVALS/eval_results.json`.

---

## 🛡️ Security

- Passwords hashed with **Argon2** (memory-hard algorithm)
- **JWT** tokens for stateless authentication
- **PII Detection** using `cbx-indic-pii-extractor-17M` — queries with sensitive data are blocked before reaching the LLM
- System prompt hardening against **prompt injection** via retrieved documents
- Secrets managed exclusively through `.env` (never committed to version control)

---

## 🖥️ MCP Server

An optional **Model Context Protocol** server is included for IDE/agent integrations:

```bash
uv run python -m MCP_.server
```

Exposes two prompts:
- `user_hr_prompt` — the full HR Policy Assistant system prompt
- `rewrite_user_query_prompt` — the query rewriting prompt

---

## 🛠️ Tech Stack

**Backend**
- [FastAPI](https://fastapi.tiangolo.com/) — async REST API
- [LangGraph](https://github.com/langchain-ai/langgraph) — agentic RAG pipeline with stateful graph
- [LangChain](https://www.langchain.com/) — LLM orchestration, document loaders, text splitters
- [Groq](https://console.groq.com/) — ultra-fast LLM inference
- [FlashRank](https://github.com/PrithivirajDamodaran/FlashRank) — lightweight neural re-ranker
- [PGVector](https://github.com/pgvector/pgvector) + [langchain-postgres](https://github.com/langchain-ai/langchain-postgres) — vector store
- [SQLAlchemy](https://www.sqlalchemy.org/) (async) + [Alembic](https://alembic.sqlalchemy.org/) — ORM and migrations
- [HuggingFace Sentence Transformers](https://www.sbert.net/) — `all-MiniLM-L6-v2` embeddings
- [PyJWT](https://pyjwt.readthedocs.io/) + [Argon2](https://argon2-cffi.readthedocs.io/) — auth
- [MCP](https://modelcontextprotocol.io/) — Model Context Protocol server

**Frontend**
- [React 19](https://react.dev/) + [Vite](https://vitejs.dev/)
- [React Router v7](https://reactrouter.com/)

**Testing & Evaluation**
- [pytest](https://pytest.org/) + [pytest-asyncio](https://pytest-asyncio.readthedocs.io/)
- [DeepEval](https://github.com/confident-ai/deepeval) — RAG evaluation framework

---

## 📋 Development

### Running Tests

```bash
uv run pytest
```

### Linting (Frontend)

```bash
cd frontend
npm run lint
```

### Database Migrations

```bash
# Create a new migration
uv run alembic revision --autogenerate -m "description"

# Apply migrations
uv run alembic upgrade head

# Rollback one step
uv run alembic downgrade -1
```

---

