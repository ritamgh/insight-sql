<!-- Generated: 2026-04-28 | Files scanned: 1 | Token estimate: ~300 -->

# Frontend

## Streamlit App

`frontend/streamlit_app.py` — Single-page Streamlit dashboard.

## Layout

```
┌─────────────────────────────────────────────────────┐
│ InsightSQL — Agentic NL2SQL for Northwind analytics │
│                                                      │
│ [Query Form]  "Business question" [Run query]        │
│                                                      │
│ Explanation  │ Agent Trace (dataframe)               │
│ Results      │ (dataframe)                           │
│ SQL          │ (expandable)                          │
│ Agent State  │ (expandable JSON)                     │
└─────────────────────────────────────────────────────┘

Sidebar:
  - System Status (DB health)
  - Agent Stack (LangGraph / Groq / LangSmith)
  - Demo Queries (7 preset buttons)
```

## Key Interactions

1. User enters query (text input or demo button)
2. Calls `run_agent_pipeline(query)` from controller
3. Displays: explanation → error/status → agent trace → result rows → generated SQL → full state

## Example Queries

"Top customers by revenue", "Recent orders", "Best products", "Sales by category", "Employees by revenue", "Average freight by shipper", "Highest sold car model" (out-of-scope test)
