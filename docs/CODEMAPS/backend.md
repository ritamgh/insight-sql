<!-- Generated: 2026-04-28 | Files scanned: 22 | Token estimate: ~700 -->

# Backend Architecture

## Agent Pipeline (7 agents)

| Agent | File | LLM? | Purpose |
|-------|------|------|---------|
| Disambiguation | `agents/disambiguation_agent.py` | No | Resolves vague terms (top/recent/best) with defaults |
| Domain Guard | `agents/domain_guard_agent.py` | No | Rejects out-of-scope questions via keyword matching |
| Retrieval | `agents/retrieval_agent.py` | No | Selects relevant schema snippets from Northwind |
| SQL Generation | `agents/sql_generation_agent.py` | Groq | Generates SELECT via Groq LLM |
| Validation | `agents/validation_agent.py` | No | Safety check + PostgreSQL EXPLAIN (or demo fallback) |
| Execution | `agents/execution_agent.py` | No | Runs SQL against Postgres or pandas demo backend |
| Explanation | `agents/explanation_agent.py` | Groq | Summarizes results in plain English |

## Controller

`backend/app/controller.py` — LangGraph `StateGraph` orchestrating all agents.

- `run_agent_pipeline(query, max_attempts=2)` — main entry point
- `_build_workflow()` — cached graph construction (`@lru_cache`)
- `_route_after_domain_guard()` — conditional: in-scope → retrieval, out-of-scope → explanation
- `_route_after_validation()` — conditional: valid → execution, retryable → sql_generation, exhausted → explanation

## State Schema

`backend/app/schemas/state.py` — `AgentState(TypedDict)` with keys:
`query`, `refined_query`, `is_ambiguous`, `clarification`, `out_of_scope`, `schema`, `sql`, `validation`, `retry_count`, `max_attempts`, `result`, `explanation`, `error`, `data_source`, `agent_trace`, `db_health`

## Services

`backend/app/services/llm.py`:
- `generate_sql_with_groq(refined_query, schema_context, last_error)` → SQL string
- `generate_explanation_with_groq(query, sql, rows)` → explanation string
- `_extract_sql(text)` — strips markdown fences from LLM output

## Database Layer

`backend/app/db/`:
- `connection.py` — `get_connection()`, `explain_query(sql)`, `fetch_rows(sql)` via psycopg2
- `health.py` — `check_database_health()`, URL masking, friendly error messages
- `demo_executor.py` — Pattern-matches SQL to pandas computations (8 query patterns)
- `demo_data.py` — Hardcoded Northwind DataFrames for demo mode
- `northwind_schema.py` — Schema snippets + keyword→table mapping for retrieval

## Prompts

`backend/app/prompts/sql_generation.py`:
- `SQL_GENERATION_SYSTEM_PROMPT` — rules for SQL generation
- `build_sql_generation_prompt(query, schema, error)` — assembles user prompt
- `EXPLANATION_SYSTEM_PROMPT` — rules for explanation
- `build_explanation_prompt(query, sql, rows)` — assembles explanation prompt

## Configuration

`backend/app/core/config.py` — Frozen `Settings` dataclass from env vars:
`DATABASE_URL`, `GROQ_API_KEY`, `GROQ_MODEL`, `STATEMENT_TIMEOUT_MS`, `LANGSMITH_*`
