<!-- Generated: 2026-04-29 | Files scanned: 1 | Token estimate: ~450 -->

# Frontend

## Streamlit App

`frontend/streamlit_app.py` (652 lines) — Single-page Streamlit dashboard with custom CSS and session state management.

## Layout

```
┌─────────────────────────────────────────────────────────┐
│ InsightSQL — Northwind analytics agent  [status pills]  │
│                                                          │
│ [Query Form]  "Business question" [Run query]            │
│                                                          │
│ [Clarification form] (shown when pending_clarification)  │
│                                                          │
│ Metrics row: Rows | Data Source | Validation | Retries   │
│ Explanation (styled panel)                                │
│ Cardinality warning / status message (conditional)       │
│ Disambiguation / clarification notice (conditional)      │
│ Results (dataframe)                                       │
│                                                          │
│ Tabs: [Generated SQL | Agent Trace | RAG Context | State]│
│   SQL tab:      generated SQL code block                  │
│   Trace tab:    agent trace dataframe                     │
│   Context tab:  schema chunks (left) + examples (right)  │
│   State tab:    full AgentState JSON                      │
└─────────────────────────────────────────────────────────┘

Sidebar:
  - System Status (DB health + connection URL)
  - Agent Stack (LangGraph / Groq / LangSmith)
  - Demo Queries (7 preset buttons)
  - Query History (last 10, session-scoped)
```

## Status Pills (hero strip)

- "PostgreSQL connected" (green) or "Demo data fallback" (amber)
- "Groq configured" (green) or "Groq key missing" (amber)
- "LangSmith on" (green) or "LangSmith off" (gray)

## Key Interactions

1. User enters query (text input or demo button)
2. `run_agent_pipeline(query)` — if `pending_clarification`, shows clarification form
3. User submits clarification → `run_agent_pipeline(prior_state, user_clarification)` (max 2 rounds)
4. Renders: metrics row → explanation panel → warnings → status → results → tabbed details

## Session State

- `last_state` — most recent AgentState for rendering
- `pending_state` — paused state awaiting user clarification
- `history` — `deque(maxlen=10)` of past queries
