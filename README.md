# InsightSQL

Agentic NL2SQL prototype that translates natural-language business questions into SQL, executes them against a Northwind database, and returns plain-English explanations.

Built with **LangGraph** (agent orchestration), **Groq** (LLM inference), **ChromaDB** (RAG retrieval), and **Streamlit** (UI).

## Architecture

```
User (Streamlit)
  │
  ├─ Clarification loop (max 2 rounds)
  │
  ▼
Controller (LangGraph)
  │
  ├─ Disambiguation   (LLM clarification + fallback)
  ├─ Domain Guard     (keyword filter)
  ├─ Retrieval        (ChromaDB semantic + BM25 hybrid)
  ├─ SQL Generation   (Groq LLM)
  ├─ Validation       (4 layers: safety→schema→semantic→EXPLAIN)
  ├─ Execution        (PostgreSQL / demo fallback)
  └─ Explanation      (Groq LLM)
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
- "Monthly sales revenue"
- "Customers with more than ten orders"

The sidebar shows database connection status, agent stack info, and clickable demo queries. If your question is ambiguous, the app asks for clarification (up to 2 rounds) before proceeding. After running a query, the app displays the explanation, agent trace, result table, and generated SQL.

## Agent Pipeline

Each agent is a pure function that transforms a shared `AgentState` dict:

| Agent | Role | LLM |
|-------|------|-----|
| Disambiguation | Resolves vague terms via LLM; asks clarification questions (max 2 rounds); falls back to default assumptions | Yes |
| Domain Guard | Blocks questions outside Northwind domain (e.g. cars, weather) | No |
| Retrieval | ChromaDB semantic + BM25 hybrid search for relevant schema and example SQL | No |
| SQL Generation | Generates a `SELECT` statement via Groq with schema context and retrieved examples | Yes |
| Validation | 4-layer check: safety (sqlglot AST) → schema (AST + alias) → semantic (GROUP BY) → EXPLAIN | No |
| Execution | Runs SQL against PostgreSQL or pandas demo backend | No |
| Explanation | Summarizes results in plain English via Groq | Yes |

The controller retries SQL generation up to `max_attempts` times when validation fails with a retryable error.

## RAG Module

Hybrid retrieval over a ChromaDB persistent index (`.rag_index/`):

| Collection | Contents | K |
|------------|----------|---|
| `schema_chunks` | Column-level chunks from full Northwind schema (one per column, with FK info) | 3 |
| `examples` | 20 hand-authored question-to-SQL example pairs | 2 |

Retrieval merges semantic search (all-MiniLM-L6-v2 embeddings) with BM25 keyword matching, prioritizing semantic results.

Build or rebuild the index:

```bash
python scripts/build_rag_index.py
```

## Evaluation Framework

Golden-set evaluation with 50 questions across 6 categories:

| Category | Count |
|----------|-------|
| Simple SELECT | 10 |
| Two-table JOIN | 10 |
| Multi-table JOIN (3+) | 10 |
| Aggregation | 10 |
| GROUP BY + HAVING | 5 |
| Time-based | 5 |

Metrics: execution accuracy, execution success, error recovery, latency.

Run evaluations:

```bash
python scripts/run_eval.py
```

Results are written to `evaluation/results/` as JSONL.

## Database

**PostgreSQL 16** running in Docker with the Northwind sample dataset.

### Tables

`categories`, `customers`, `employees`, `orders`, `order_details`, `products`, `shippers`, `suppliers`, `region`, `territories`, `employee_territories`, `customer_customer_demo`, `customer_demographics`, `us_states`

### Key relationship

```sql
revenue = order_details.unit_price * quantity * (1 - discount)
```

## Testing

```bash
pytest
```

Tests are in `tests/` and cover individual agents (`test_agents.py`), the full controller pipeline (`test_controller.py`), RAG retrieval (`test_rag_retrieval.py`), validation layers (`test_validation_layers.py`), disambiguation (`test_disambiguation_llm.py`), demo executor (`test_demo_executor.py`), cardinality checks (`test_cardinality.py`), and evaluation normalization (`test_eval_normalize.py`). No live Postgres or Groq API key required — all external calls are mocked.

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
│       ├── rag/             # ChromaDB index, chunks, examples, retrieval
│       ├── schemas/state.py # AgentState TypedDict
│       └── services/llm.py  # Groq integration
├── evaluation/              # Golden dataset, metrics, configurations, runner
├── frontend/
│   └── streamlit_app.py     # Streamlit dashboard
├── scripts/
│   ├── build_rag_index.py   # Build ChromaDB index
│   └── run_eval.py          # Run golden-set evaluation
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
