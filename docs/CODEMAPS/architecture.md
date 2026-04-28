<!-- Generated: 2026-04-28 | Files scanned: 30 | Token estimate: ~600 -->

# Architecture

InsightSQL — Agentic NL2SQL prototype for Northwind analytics.

## System Overview

```
User (Streamlit) → Controller (LangGraph) → Agent Pipeline → PostgreSQL / Demo Data
                          │
                          └→ Groq LLM (SQL generation, explanation)
```

## Agent Pipeline (LangGraph StateGraph)

```
START → Disambiguation → Domain Guard → [in-scope?]
                                           │
                                   yes → Retrieval → SQL Gen → Validation → [valid?]
                                                                            │
                                                                     yes → Execution → Explanation → END
                                                                     no  → [retry?] → SQL Gen (max 2x)
                                                                           │
                                                                     exhausted → Explanation → END
                                   no → Explanation → END
```

## Routing Logic

| Node | Condition | Route |
|------|-----------|-------|
| Domain Guard | `out_of_scope=true` | → Explanation (skip pipeline) |
| Domain Guard | in scope | → Retrieval |
| Validation | `is_valid=true` | → Execution |
| Validation | `is_valid=false` + retryable + retries left | → SQL Generation |
| Validation | `is_valid=false` + exhausted retries | → Explanation |

## Key Design Decisions

- **Dual execution backend**: Falls back to pandas-based demo executor when PostgreSQL is unavailable
- **Read-only safety**: Validation agent blocks all DML/DDL; only SELECT/WITH allowed
- **Stateless agents**: Each agent is a pure function `(state) → state`, no side effects
- **LLM via Groq**: SQL generation and explanation use Groq API (Llama 3.3 70B)
- **Observability**: LangSmith tracing on all agent nodes

## Entry Point

`run_agent_pipeline(query, max_attempts=2) → AgentState` in `backend/app/controller.py`
