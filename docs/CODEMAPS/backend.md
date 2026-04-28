<!-- Generated: 2026-04-29 | Files scanned: 52 | Token estimate: ~900 -->

# Backend Architecture

## Agent Pipeline (7 agents)

| Agent | File | LLM? | Purpose |
|-------|------|------|---------|
| Disambiguation | `agents/disambiguation_agent.py` (346 lines) | Groq | LLM clarification + context-aware merge (`merge_clarification()`) + deterministic fallback |
| Domain Guard | `agents/domain_guard_agent.py` | No | Rejects out-of-scope questions via keyword matching |
| Retrieval | `agents/retrieval_agent.py` | No | Hybrid ChromaDB semantic + BM25 (or legacy keyword fallback) |
| SQL Generation | `agents/sql_generation_agent.py` | Groq | Generates SELECT via Groq LLM with schema + examples + FK rules |
| Validation | `agents/validation_agent.py` | No | 4-layer: safety (sqlglot) → schema (AST) → semantic → EXPLAIN |
| Execution | `agents/execution_agent.py` | No | Runs SQL against Postgres or pandas demo backend + cardinality check |
| Explanation | `agents/explanation_agent.py` | Groq | Summarizes results in plain English |

## Controller

`backend/app/controller.py` — LangGraph `StateGraph` orchestrating all agents.

- `run_agent_pipeline(query, max_attempts=3, *, prior_state, user_clarification, use_rag, use_validation_layers)` — main entry point
- `_build_workflow()` — cached graph construction (`@lru_cache`)
- `_route_after_disambiguation()` — conditional: pending clarification → END, else → domain guard
- `_route_after_domain_guard()` — conditional: in-scope → retrieval, out-of-scope → explanation
- `_route_after_validation()` — conditional: valid → execution, retryable → sql_generation, exhausted → explanation

## State Schema

`backend/app/schemas/state.py` — `AgentState(TypedDict)` with 30+ keys including:
- Pipeline control: `query`, `refined_query`, `sql`, `error`, `result`, `explanation`
- Disambiguation: `is_ambiguous`, `clarification_question`, `clarification_attempts`, `pending_clarification`, `disambiguation_triggered`, `user_clarification`, `applied_clarification`
- RAG: `retrieved_schema_chunks`, `retrieved_examples`, `use_rag`
- Validation: `validation_layers_triggered`, `failed_layer`, `use_validation_layers`
- Execution: `data_source`, `cardinality_warning`, `last_sql`

## RAG Module

`backend/app/rag/`:
- `index.py` — ChromaDB persistent index (schema_chunks + examples collections), embedder (`all-MiniLM-L6-v2`)
- `chunks.py` — Builds column-level chunks from `northwind_full_schema.py`
- `examples.py` — 18 hand-written Q→SQL example pairs
- `retrieval.py` — `semantic_search()`, `bm25_search()`, `hybrid_merge()` (semantic priority, K=3 schema / K=2 examples)

## Services

`backend/app/services/llm.py` (132 lines):
- `generate_sql_with_groq(refined_query, schema_context, retrieved_examples, last_error, last_sql)` → SQL
- `generate_explanation_with_groq(query, sql, rows)` → explanation
- `disambiguate_with_groq(query, schema_summary)` → `{is_ambiguous, clarification_question, default_assumption}`
- `_extract_json()` — parses LLM JSON output with fallback
- Lazy langchain imports (wrapped in try/except)

## Prompts

`backend/app/prompts/`:
- `sql_generation.py` — System prompt with FK direction, time rules, example conflict guard; retry format includes `PREVIOUS SQL` + `ERROR`
- `disambiguation.py` — System prompt for LLM disambiguation with Northwind-specific policies

## Database Layer

`backend/app/db/`:
- `connection.py` — `get_connection()`, `explain_query(sql)`, `fetch_rows(sql)` via psycopg2
- `health.py` — `check_database_health()`, URL masking, friendly error messages
- `demo_executor.py` — Pattern-matches SQL to pandas computations (8 query patterns)
- `demo_data.py` — Hardcoded Northwind DataFrames for demo mode
- `northwind_schema.py` — Legacy keyword→table mapping for non-RAG retrieval
- `northwind_full_schema.py` — Full schema metadata: `TABLE_COLUMNS`, `PRIMARY_KEYS`, `FOREIGN_KEYS` (13 tuples)

## Configuration

`backend/app/core/config.py` — Frozen `Settings` dataclass from env vars:
`DATABASE_URL`, `GROQ_API_KEY`, `GROQ_MODEL`, `STATEMENT_TIMEOUT_MS`, `LANGSMITH_*`
