<!-- Generated: 2026-04-29 | Files scanned: 52 | Token estimate: ~400 -->

# Dependencies

## External Services

| Service | Purpose | Config |
|---------|---------|--------|
| Groq API | SQL generation + explanation + disambiguation (Llama 3.3 70B) | `GROQ_API_KEY`, `GROQ_MODEL` |
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
| pandas | ≥2.2.0 | Demo data backend + evaluation |
| psycopg2-binary | ≥2.9.9 | PostgreSQL driver |
| chromadb | ≥0.5.0 | Persistent vector store for RAG |
| sentence-transformers | ≥3.0.0 | Embeddings (`all-MiniLM-L6-v2`) |
| sqlglot | ≥25.0.0 | SQL AST parsing for validation |
| rank_bm25 | ≥0.2.2 | BM25 lexical retrieval |
| numpy | ≥1.26.0 | Numerical operations |
| matplotlib | ≥3.8.0 | Evaluation bar charts |
| pytest | ≥8.2.0 | Testing |

## Architecture Dependencies

```
streamlit_app.py
  └→ controller.py (LangGraph)
       ├→ agents/disambiguation_agent.py → services/llm.py (Groq)
       ├→ agents/retrieval_agent.py
       │    ├→ rag/retrieval.py (semantic + BM25 hybrid)
       │    ├→ rag/index.py → ChromaDB
       │    └→ db/northwind_full_schema.py (FK lines)
       ├→ agents/sql_generation_agent.py → services/llm.py (Groq)
       ├→ agents/validation_agent.py → sqlglot + db/connection.py
       ├→ agents/execution_agent.py → db/connection.py or db/demo_executor.py
       └→ agents/explanation_agent.py → services/llm.py (Groq)

scripts/build_rag_index.py → rag/index.py → rag/chunks.py + rag/examples.py
scripts/run_eval.py → evaluation/runner.py → evaluation/metrics.py + evaluation/normalize.py
```

## Evaluation Pipeline

`scripts/run_eval.py` — Runs 3 configurations (baseline, rag, full) against golden dataset.

`evaluation/`:
- `configurations.py` — `run_baseline()`, `run_rag()`, `run_full()` (passes `use_rag`/`use_validation_layers` flags)
- `runner.py` — Iterates golden questions × configs, writes JSONL with metrics
- `metrics.py` — `execution_accuracy()`, `execution_success()`, `error_recovery()`, `latency_ms()`
- `normalize.py` — 3-step result normalization (sort, round, frozenset comparison)
- `report.py` — Generates CSV summary + matplotlib bar charts from JSONL

## Environment Variables

See `.env.example`: `DATABASE_URL`, `DATABASE_CONNECT_TIMEOUT_SECONDS`, `STATEMENT_TIMEOUT_MS`, `GROQ_API_KEY`, `GROQ_MODEL`, `GROQ_REQUEST_TIMEOUT_SECONDS`, `LANGSMITH_TRACING`, `LANGSMITH_API_KEY`, `LANGSMITH_PROJECT`
