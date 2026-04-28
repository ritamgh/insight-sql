# InsightSQL

Agentic NL2SQL prototype that translates natural-language business questions into SQL, executes them against a Northwind database, and returns plain-English explanations.

Built with **LangGraph** (agent orchestration), **Groq** (LLM inference), and **Streamlit** (UI).

## Architecture

```
User (Streamlit)
  │
  ▼
LangGraph Controller ──► 7-Agent Pipeline
  │
  ├─ Disambiguation Agent   (resolves vague terms)
  ├─ Domain Guard Agent     (rejects out-of-scope questions)
  ├─ Retrieval Agent        (selects relevant schema)
  ├─ SQL Generation Agent   (Groq LLM → SELECT)
  ├─ Validation Agent       (safety check + EXPLAIN)
  ├─ Execution Agent        (Postgres or demo fallback)
  └─ Explanation Agent      (Groq LLM → summary)
```

When PostgreSQL is unavailable, the app automatically falls back to a pandas-based demo executor so the full pipeline still works.

## Prerequisites

- Python 3.11+
- Docker (optional, for PostgreSQL)
- Groq API key — get one at [console.groq.com](https://console.groq.com)

## Setup

### 1. Clone and install dependencies

```bash
git clone <repo-url> && cd insight-sql
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env` and add your Groq API key:

```
GROQ_API_KEY=gsk_...
```

### 3. Start PostgreSQL (optional)

```bash
docker compose up -d
```

This starts a PostgreSQL 16 container on port **5433** with the Northwind dataset pre-loaded. The app works without it — demo data is used as a fallback.

### 4. Run the app

```bash
streamlit run frontend/streamlit_app.py
```

## Usage

Ask a business question in natural language:

- "Top customers by revenue"
- "Recent orders"
- "Best products"
- "Sales by category"
- "Employees by revenue"
- "Average freight by shipper"

The sidebar shows database connection status, agent stack info, and clickable demo queries. After running a query, the app displays the explanation, agent trace, result table, and generated SQL.

## Agent Pipeline

Each agent is a pure function that transforms a shared `AgentState` dict:

| Agent | Role | LLM |
|-------|------|-----|
| Disambiguation | Resolves "top", "recent", "best" with default assumptions | No |
| Domain Guard | Blocks questions outside Northwind domain (e.g. cars, weather) | No |
| Retrieval | Keyword-maps query to relevant schema snippets | No |
| SQL Generation | Generates a `SELECT` statement via Groq | Yes |
| Validation | Blocks DML/DDL, runs `EXPLAIN`, falls back to demo if DB down | No |
| Execution | Runs SQL against PostgreSQL or pandas demo backend | No |
| Explanation | Summarizes results in plain English via Groq | Yes |

The controller retries SQL generation up to `max_attempts` times when validation fails with a retryable error.

## Database

**PostgreSQL 16** running in Docker with the Northwind sample dataset.

### Tables

`categories`, `customers`, `employees`, `orders`, `order_details`, `products`, `shippers`, `suppliers`

### Key relationship

```sql
revenue = order_details.unit_price * quantity * (1 - discount)
```

## Testing

```bash
pytest
```

Tests are in `tests/` and cover individual agents (`test_agents.py`) and the full controller pipeline (`test_controller.py`). No live Postgres or Groq API key required — all external calls are mocked.

## Project Structure

```
insight-sql/
├── backend/
│   └── app/
│       ├── agents/          # 7 agent modules
│       ├── controller.py    # LangGraph orchestration
│       ├── core/config.py   # Settings from env vars
│       ├── db/              # Connection, health, demo data, schema
│       ├── prompts/         # LLM prompt templates
│       ├── schemas/state.py # AgentState TypedDict
│       └── services/llm.py  # Groq integration
├── frontend/
│   └── streamlit_app.py     # Streamlit dashboard
├── data/
│   └── postgres/init/       # Northwind SQL seed
├── tests/                   # pytest tests
├── docker-compose.yml       # PostgreSQL service
├── requirements.txt
└── .env.example
```

## Configuration

All settings are env vars loaded from `.env`:

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql://postgres:postgres@localhost:5432/northwind` | PostgreSQL connection string |
| `DATABASE_CONNECT_TIMEOUT_SECONDS` | `2` | Connection timeout |
| `STATEMENT_TIMEOUT_MS` | `10000` | Per-query execution timeout |
| `GROQ_API_KEY` | (required) | Groq API key for LLM calls |
| `GROQ_MODEL` | `llama-3.3-70b-versatile` | Groq model to use |
| `GROQ_REQUEST_TIMEOUT_SECONDS` | `30` | LLM request timeout |
| `LANGSMITH_TRACING` | `false` | Enable LangSmith tracing |
| `LANGSMITH_API_KEY` | (optional) | LangSmith API key |
| `LANGSMITH_PROJECT` | `InsightSQL-AgentOps` | LangSmith project name |
