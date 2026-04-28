<!-- Generated: 2026-04-28 | Files scanned: 30 | Token estimate: ~350 -->

# Dependencies

## External Services

| Service | Purpose | Config |
|---------|---------|--------|
| Groq API | SQL generation + explanation (Llama 3.3 70B) | `GROQ_API_KEY`, `GROQ_MODEL` |
| PostgreSQL 16 | Primary data store (Northwind) | `DATABASE_URL`, Docker Compose port 5433 |
| LangSmith | Agent tracing & observability | `LANGSMITH_TRACING`, `LANGSMITH_API_KEY` |

## Python Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| langchain | ≥1.2.0 | Agent framework foundation |
| langchain-core | ≥1.2.0 | Prompts, message types |
| langchain-groq | ≥1.1.0 | Groq LLM integration |
| langgraph | ≥1.0.5 | StateGraph workflow orchestration |
| langsmith | ≥0.4.0 | Tracing decorator (`@traceable`) |
| streamlit | ≥1.36.0 | Web UI |
| pandas | ≥2.2.0 | Demo data backend |
| psycopg2-binary | ≥2.9.9 | PostgreSQL driver |
| pytest | ≥8.2.0 | Testing |

## Architecture Dependencies

```
streamlit_app.py
  └→ controller.py (LangGraph)
       ├→ agents/*.py (7 agents)
       │    ├→ services/llm.py → Groq API
       │    ├→ db/connection.py → PostgreSQL
       │    └→ db/northwind_schema.py (hardcoded schema)
       └→ schemas/state.py (AgentState)
```

## Fallback Behavior

When PostgreSQL is unavailable:
1. Validation agent detects connection error → sets `execution_backend="demo"`
2. Execution agent routes to `demo_executor.py` (pandas-based)
3. App remains fully functional with demo data

## Environment Variables

See `.env.example` for required configuration:
- `DATABASE_URL` — PostgreSQL connection string
- `GROQ_API_KEY` — Required for SQL generation
- `GROQ_MODEL` — Default: `llama-3.3-70b-versatile`
- `LANGSMITH_*` — Optional tracing
