<!-- Generated: 2026-04-29 | Files scanned: 52 | Token estimate: ~700 -->

# Architecture

InsightSQL — Agentic NL2SQL prototype for Northwind analytics.

## System Overview

```
User (Streamlit)
  │
  ├─ Clarification loop (max 2 rounds)
  │
  ▼
Controller (LangGraph)
  │
  ├─ Disambiguation (LLM + fallback)
  ├─ Domain Guard (keyword filter)
  ├─ Retrieval (ChromaDB semantic + BM25 hybrid)
  ├─ SQL Generation (Groq LLM)
  ├─ Validation (4 layers: safety→schema→semantic→EXPLAIN)
  ├─ Execution (PostgreSQL / demo fallback)
  └─ Explanation (Groq LLM)
```

## Agent Pipeline (LangGraph StateGraph)

```
START → Disambiguation → [ambiguous?]
                              │
                       yes + attempts < 2 → END (return clarification to UI)
                       yes + attempts = 2 → Domain Guard (with default assumption)
                       no → Domain Guard → [in-scope?]
                                                   │
                                           yes → Retrieval → SQL Gen → Validation → [valid?]
                                                                                    │
                                                                             yes → Execution → Explanation → END
                                                                             no  → [retry < 3] → SQL Gen
                                                                             exhausted → Explanation → END
                                           no → Explanation → END
```

## Routing Logic

| Node | Condition | Route |
|------|-----------|-------|
| Disambiguation | `pending_clarification=true` | → END (await user input) |
| Disambiguation | clear or max attempts | → Domain Guard |
| Domain Guard | `out_of_scope=true` | → Explanation |
| Domain Guard | in scope | → Retrieval |
| Validation | `is_valid=true` | → Execution |
| Validation | `is_valid=false` + retryable + retries < 3 | → SQL Generation |
| Validation | `is_valid=false` + exhausted | → Explanation |

## Key Design Decisions

- **Dual execution backend**: Falls back to pandas-based demo executor when PostgreSQL is unavailable
- **Four-layer validation**: safety (sqlglot AST) → schema (AST + alias resolution) → semantic (GROUP BY check) → EXPLAIN
- **Hybrid RAG**: ChromaDB semantic search + BM25, merged with semantic priority
- **Interactive disambiguation**: LLM-based with clarification loop, cap at 2 attempts
- **Configurable pipeline**: `use_rag` and `use_validation_layers` flags enable ablation evaluation
- **Observability**: LangSmith tracing on all agent nodes

## Entry Point

`run_agent_pipeline(query, max_attempts=3, use_rag=True, use_validation_layers=True, prior_state=None, user_clarification=None)` in `backend/app/controller.py`
