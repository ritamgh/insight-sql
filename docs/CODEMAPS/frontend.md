<!-- Generated: 2026-04-28 | Files scanned: 1 | Token estimate: ~400 -->

# Frontend

## Streamlit App

`frontend/streamlit_app.py` — Single-page Streamlit dashboard with session state management.

## Layout

```
┌─────────────────────────────────────────────────────┐
│ InsightSQL — Agentic NL2SQL for Northwind analytics │
│                                                      │
│ [Query Form]  "Business question" [Run query]        │
│                                                      │
│ [Clarification form] (shown when pending_clarification)│
│                                                      │
│ Explanation │ Cardinality warning (conditional)       │
│ Status (demo/postgres/out-of-scope)                  │
│ Default assumption notice (conditional)              │
│ Agent Trace (dataframe)                              │
│ Results (dataframe)                                  │
│ Retrieved schema context (expander, top-3)           │
│ Retrieved examples (expander, top-2)                 │
│ Generated SQL (expander)                             │
│ Agent State (expander, JSON)                         │
└─────────────────────────────────────────────────────┘

Sidebar:
  - System Status (DB health)
  - Agent Stack (LangGraph / Groq / LangSmith)
  - Demo Queries (7 preset buttons)
  - Query History (last 10, session-scoped)
```

## Key Interactions

1. User enters query (text input or demo button)
2. `run_agent_pipeline(query)` — if `pending_clarification`, shows clarification form
3. User submits clarification → `run_agent_pipeline(prior_state, user_clarification)` (max 2 rounds)
4. Displays: explanation → cardinality warning → status → default assumption → trace → results → schema → examples → SQL → state

## Session State

- `last_state` — most recent AgentState for rendering
- `pending_state` — paused state awaiting user clarification
- `history` — `deque(maxlen=10)` of past queries
