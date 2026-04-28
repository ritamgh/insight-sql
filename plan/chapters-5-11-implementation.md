# InsightSQL — Chapters 5–11 Feature Implementation Plan

## Context

The InsightSQL prototype has a 7-agent NL2SQL pipeline. The following capabilities from Chapters 5–11 of the project report are missing from code:

- **Ch 5 — Disambiguation**: hardcoded keyword regex, no LLM, no clarification loop, no attempt cap
- **Ch 6 — RAG Layer**: keyword-substring lookups only, no embeddings, no BM25, no example bank
- **Ch 7 — SQL Gen Prompt**: no FK section, no examples, no time-rules, retry doesn't include failed SQL
- **Ch 8 — Validation**: regex + EXPLAIN only, no sqlglot AST, no schema/semantic layers, retry budget=2 not 3
- **Ch 9 — Execution/UI**: no cardinality check, no clarification UI loop, no query history, no chunk panels
- **Ch 10–11 — Eval**: no golden dataset, no normalization, no metrics, no config comparison

Not installed today: `chromadb`, `sentence-transformers`, `sqlglot`, `rank_bm25`. No `evaluation/` or `scripts/` directories exist.

**Decisions locked in:**
- Author both Q→SQL examples (18 pairs) and 50-question golden dataset
- Embeddings: `all-MiniLM-L6-v2`
- Clarification loop: pause-and-resume via Streamlit `session_state`
- One plan, phased execution

---

## Phase 0 — Dependencies & State Schema

### `requirements.txt` — add:
```
chromadb>=0.5.0
sentence-transformers>=3.0.0
sqlglot>=25.0.0
rank_bm25>=0.2.2
numpy>=1.26.0
matplotlib>=3.8.0
```

### `backend/app/schemas/state.py` — extend `AgentState` with:
```python
clarification_question: str
clarification_attempts: int          # cap 2
pending_clarification: bool
disambiguation_triggered: bool
retrieved_examples: list[dict[str, Any]]
retrieved_schema_chunks: list[dict[str, Any]]
validation_layers_triggered: list[str]
failed_layer: str | None
cardinality_warning: str | None
last_sql: str                        # passed into retry prompt
```

### `backend/app/controller.py:initial_state` — seed defaults for all new keys; bump `max_attempts` default 2 → 3.

---

## Phase 1 — RAG Corpus & Vector Index

**New** `backend/app/db/northwind_full_schema.py`
- `TABLE_COLUMNS: dict[str, dict[str, str]]` — all 14 Northwind tables with column types/descriptions (parsed from `data/postgres/init/01_northwind_demo.sql`)
- `FOREIGN_KEYS: list[tuple[str, str, str, str]]` — 13 FK relationships as `(child_table, child_col, parent_table, parent_col)`
- Used by: validation schema layer (Phase 6) and prompt FK block (Phase 5)

**New** `backend/app/rag/` package:
- `chunks.py` — `build_column_chunks() -> list[dict]`: one chunk per (table, column), formatted as `"Table: <t>. Column: <c>. Type: <type>. Description: <desc>. FKs: <list>"`. ~80–100 chunks.
- `examples.py` — `EXAMPLE_PAIRS: list[dict[str, str]]`: 18 hand-authored Q→SQL pairs covering 4 simple SELECT, 4 two-table joins, 3 three-table joins, 3 aggregates, 2 GROUP BY/HAVING, 2 time-based.
- `index.py`:
  - `get_embedder()` — module-level cached `SentenceTransformer("all-MiniLM-L6-v2")`
  - `build_chroma_indexes(persist_dir: Path) -> None` — two `chromadb.PersistentClient` collections: `schema_chunks`, `examples`
  - `load_chroma_indexes(persist_dir: Path)` — returns collection handles; raises `RAGIndexMissing` if absent
- `retrieval.py`:
  - `semantic_search(collection, query, k) -> list[dict]`
  - `bm25_search(corpus_texts, query, k) -> list[dict]`
  - `hybrid_merge(semantic_hits, bm25_hits, k) -> list[dict]` — semantic-priority, dedup by id

**New** `scripts/build_rag_index.py` — CLI: `build_chroma_indexes(Path(".rag_index"))`. Idempotent.

---

## Phase 2 — LLM-based Disambiguation (Chapter 5)

**New** `backend/app/prompts/disambiguation.py`:
- `DISAMBIGUATION_SYSTEM_PROMPT` — instructs LLM to return strict JSON:
  ```json
  {"is_ambiguous": bool, "clarification_question": str, "default_assumption": str}
  ```
- `build_disambiguation_prompt(query, schema_summary)`

**Modify** `backend/app/services/llm.py`:
- Add `disambiguate_with_groq(query, schema_summary) -> dict`
- Add `_extract_json(text) -> dict` — locates first `{...}` block, parses, validates three keys; fallback returns `{"is_ambiguous": False, ...}`

**Rewrite** `backend/app/agents/disambiguation_agent.py`:
- `clarification_attempts == 0`: call `disambiguate_with_groq`
  - `is_ambiguous=True` → set `pending_clarification=True`, store `clarification_question`, return early
  - `is_ambiguous=False` → set `refined_query = query`
- `clarification_attempts > 0` (resume): combine `original_query + " — clarification: " + user_answer`; rerun; if still ambiguous and `attempts >= 2` → apply `default_assumption`, set `disambiguation_triggered=True`
- Log `disambiguation_triggered` and `clarification_attempts` to `agent_trace`

**Modify** `backend/app/controller.py`:
- Add `_route_after_disambiguation(state)`: `pending_clarification` → `END`; else → `domain_guard`
- Conditional edge from `disambiguation` node using that router
- Extend `run_agent_pipeline(query, max_attempts=3, *, prior_state=None, user_clarification=None)`:
  - If `prior_state + user_clarification`: merge, increment `clarification_attempts`, invoke graph

---

## Phase 3 — Streamlit Pause-and-Resume Clarification (Chapter 9, part 1)

**Modify** `frontend/streamlit_app.py`:
- After pipeline run, if `pending_clarification=True`: stash state in `st.session_state["pending_state"]`, render clarification panel (question + text input + Submit)
- On submit: call `run_agent_pipeline(prior_state=..., user_clarification=answer)`, clear pending state, render result
- Cap clarification UI at 2 attempts
- When `disambiguation_triggered=True` (not pending): show info banner: `"Default assumption applied: {clarification}"`

---

## Phase 4 — Hybrid Retrieval Agent (Chapter 6)

**Rewrite** `backend/app/agents/retrieval_agent.py`:
- Lazy-load Chroma collections at module scope (cached)
- Schema: `semantic_search(k=5)` + `bm25_search(k=5)` → `hybrid_merge(k=3)` → `state["retrieved_schema_chunks"]`
- Examples: same flow → `state["retrieved_examples"]` (k=2)
- Build `state["schema"]`:
  - "RELEVANT COLUMNS:" block from top-3 schema chunks
  - "FOREIGN KEY RELATIONSHIPS:" block from `northwind_full_schema.FOREIGN_KEYS`
- Fallback: `RAGIndexMissing` → log warning, use legacy `select_schema_context`

---

## Phase 5 — SQL Generation Prompt (Chapter 7)

**Modify** `backend/app/prompts/sql_generation.py`:

Add to `SQL_GENERATION_SYSTEM_PROMPT`:
```
FOREIGN KEY RULE: child_table.fk_column = parent_table.pk_column (never reversed).
JOIN RULE: Every multi-table query MUST use explicit JOIN ... ON. No implicit joins (comma-separated FROM).
TIME RULES: Use EXTRACT(YEAR FROM col), DATE_TRUNC('month', col), CURRENT_DATE - INTERVAL '30 days'.
EXAMPLE CONFLICT: If a provided example conflicts with the current schema, ignore the example.
```

Update `build_sql_generation_prompt` signature:
```python
build_sql_generation_prompt(refined_query, schema_context, retrieved_examples, last_error=None, last_sql=None)
```

Assembled prompt structure:
```
SCHEMA:
{schema_context}

EXAMPLES:
Q: ...   SQL: ...
Q: ...   SQL: ...

BUSINESS QUESTION: {refined_query}

[RETRY BLOCK if retry:]
PREVIOUS SQL:
{last_sql}
ERROR: {last_error}
Fix the SQL above.

Return only SQL.
```

**Modify** `backend/app/agents/sql_generation_agent.py` — pass `retrieved_examples` and `state["sql"]` (→ `last_sql`) on retry.

**Modify** `backend/app/services/llm.py:generate_sql_with_groq` — accept `retrieved_examples` and `last_sql`.

---

## Phase 6 — Four-Layer Validation (Chapter 8)

**Rewrite** `backend/app/agents/validation_agent.py`. Retry budget: `max_attempts=3`. Each layer appends its name to `validation_layers_triggered`.

| Layer | Method | Triggers |
|-------|--------|----------|
| 1. Safety | sqlglot AST | Reject non-`Select`/`With`, multiple statements, any `Insert`/`Update`/`Delete`/`Drop`/`Alter`/`Truncate`/`Create`/`Grant`/`Revoke`/`Copy` node |
| 2. Schema | sqlglot AST + alias resolution | Walk all table refs + column refs; resolve against `northwind_full_schema.TABLE_COLUMNS`; reject unknown table or column |
| 3. EXPLAIN | `explain_query()` | Connection error → demo fallback (`is_valid=True`); other errors → retryable |
| 4. Semantic | Conditional (GROUP BY present or 2+ tables) | Non-aggregated SELECT col not in GROUP BY; 2+ tables with no JOIN ON / WHERE join condition |

Result dict gains: `validation_layers_triggered: list[str]`, `failed_layer: str | None`, `detail: str`.

---

## Phase 7 — Execution Cardinality Check

**Modify** `backend/app/agents/execution_agent.py`:
- Replace `"limit" in sql.lower()` with sqlglot AST `Limit` node detection
- After fetch: if `len(result) >= 100` AND no aggregate function in SELECT projection (sqlglot walk for `Sum|Count|Avg|Min|Max`):
  ```python
  state["cardinality_warning"] = (
      "Result was truncated at 100 rows. Consider adding an aggregation "
      "(SUM, COUNT, AVG) or a more specific filter to narrow the result."
  )
  ```

---

## Phase 8 — Explanation + UI Polish (Chapter 9, part 2)

**Modify** `backend/app/agents/explanation_agent.py`:
- Prepend `cardinality_warning` to explanation if set
- Edge case: 1 row × 1 column → `"The answer is {value}."` (skip Groq)
- Edge case: >20 rows → prefix `"Showing the top N of M rows."`

**Modify** `frontend/streamlit_app.py`:
- **Query history**: `st.session_state["history"]` (deque, max 10) in sidebar — click to rerun
- **Retrieved-chunks expander**: "Retrieved schema context (top-3)" with text + scores
- **Retrieved-examples expander**: "Retrieved examples (top-2)"
- **Cardinality warning banner** when `state["cardinality_warning"]` is set

---

## Phase 9 — Evaluation Framework (Chapters 10–11)

**New** `evaluation/` package:

| File | Contents |
|------|----------|
| `golden_dataset.py` | `GOLDEN_QUESTIONS: list[dict]` — 50 entries: `{id, category, question, gold_sql, time_sensitive}`. Categories: 10 simple, 10 two-table, 10 multi-table, 10 aggregation, 5 GROUP BY+HAVING, 5 time-based |
| `normalize.py` | `normalize_rows(rows) -> frozenset[tuple]` — lowercase columns, round floats 2dp, lowercase strings, frozenset of sorted-key row tuples |
| `configurations.py` | Three runners: `run_baseline`, `run_rag`, `run_full` via `use_rag: bool` and `use_validation_layers: bool` kwargs threaded through controller |
| `metrics.py` | `execution_accuracy`, `execution_success`, `error_recovery`, `latency_ms` |
| `runner.py` | For each (question × config): time call, fetch gold rows, compute metrics, append JSONL: `{id, config, question, predicted_sql, gold_sql, exec_accuracy, exec_success, error_recovery, latency_ms, validation_layers_triggered, failed_layer, retry_count}`. Output: `evaluation/results/<UTC-ts>.jsonl` |
| `report.py` | Read JSONL → comparison table + `<ts>_summary.csv` + `<ts>_bars.png` (matplotlib grouped bars) |

**New** `scripts/run_eval.py` — `--config baseline|rag|full|all`.

---

## Phase 10 — Tests

Add to `tests/` (matching `pytest.ini` `testpaths = tests`):

| File | What's tested |
|------|--------------|
| `test_disambiguation_llm.py` | Monkeypatch `disambiguate_with_groq`; ambiguous → `pending_clarification`; resume increments `clarification_attempts`; cap-2 fallback applies `default_assumption` |
| `test_rag_retrieval.py` | Fake Chroma + in-memory BM25; hybrid merge order, dedup by id, k honored |
| `test_validation_layers.py` | Safety blocks `INSERT/DROP/COPY`; schema rejects unknown column; semantic rejects implicit join; EXPLAIN fallback unchanged |
| `test_cardinality.py` | 100+ rows w/o aggregate → warning; aggregate → no warning; LIMIT detected via AST |
| `test_eval_normalize.py` | Float rounding, column case, row order, frozenset equality |

Update `tests/test_controller.py` — assert new state keys propagate; `pending_clarification` short-circuits pipeline.

---

## Critical Files

### Modified
```
requirements.txt
backend/app/schemas/state.py
backend/app/controller.py
backend/app/agents/disambiguation_agent.py
backend/app/agents/retrieval_agent.py
backend/app/agents/sql_generation_agent.py
backend/app/agents/validation_agent.py
backend/app/agents/execution_agent.py
backend/app/agents/explanation_agent.py
backend/app/services/llm.py
backend/app/prompts/sql_generation.py
frontend/streamlit_app.py
tests/test_controller.py
```

### New
```
backend/app/db/northwind_full_schema.py
backend/app/rag/__init__.py
backend/app/rag/chunks.py
backend/app/rag/examples.py
backend/app/rag/index.py
backend/app/rag/retrieval.py
backend/app/prompts/disambiguation.py
evaluation/__init__.py
evaluation/golden_dataset.py
evaluation/normalize.py
evaluation/configurations.py
evaluation/metrics.py
evaluation/runner.py
evaluation/report.py
scripts/build_rag_index.py
scripts/run_eval.py
tests/test_disambiguation_llm.py
tests/test_rag_retrieval.py
tests/test_validation_layers.py
tests/test_cardinality.py
tests/test_eval_normalize.py
```

### Reused Functions
- `services/llm.py:_invoke_groq` — extended with `_extract_json` for disambiguation
- `db/connection.py:explain_query, fetch_rows` — validation layer 3, gold-row eval
- `db/health.py:is_database_connection_error` — demo fallback gating
- `db/demo_executor.py:fetch_demo_rows` — eval when Postgres absent
- `controller._state_update`, `_trace_item` — extended for new trace fields
- `frontend/streamlit_app.py:EXAMPLE_QUERIES` sidebar pattern — reused for query history

---

## Verification

1. **Bootstrap**: `pip install -r requirements.txt && python scripts/build_rag_index.py`
   → `.rag_index/` populated with `schema_chunks` + `examples` collections

2. **Tests**: `pytest -q` → all tests green

3. **Smoke (Postgres up)**: `docker compose up -d && streamlit run frontend/streamlit_app.py`
   - "Top customers by revenue" → rows + explanation
   - "Show me the data" → clarification panel; answer "by category" → results
   - "Show me the data" twice without answering → default-assumption banner
   - "Highest sold car model" → out-of-scope unchanged
   - Verify: query history sidebar, retrieved-chunks expander, cardinality warning on "All order details"

4. **Smoke (Postgres down)**: `docker compose down` → demo backend still works; banner shows demo source

5. **Validation layers (Python shell)**:
   - `validation_agent({"sql": "DROP TABLE customers"})` → blocked at safety
   - `validation_agent({"sql": "SELECT bogus_col FROM customers"})` → blocked at schema
   - `validation_agent({"sql": "SELECT c.*, o.* FROM customers c, orders o"})` → blocked at semantic

6. **Eval**: `python scripts/run_eval.py --config all` → `evaluation/results/<ts>.jsonl` + `<ts>_summary.csv`
   Expected ordering: Baseline ≤ RAG-Only ≤ Full on Execution Accuracy
