"""Execution agent — runs validated SQL against Postgres or demo backend."""
from __future__ import annotations

from backend.app.db.connection import fetch_rows
from backend.app.db.demo_executor import fetch_demo_rows
from backend.app.schemas.state import AgentState


def execution_agent(state: AgentState) -> AgentState:
    sql = _with_limit_safeguard(state.get("sql", ""))
    state["sql"] = sql
    execution_backend = (
        state.get("validation", {}).get("execution_backend")
        if isinstance(state.get("validation"), dict)
        else None
    )
    try:
        if execution_backend == "demo":
            state["result"] = fetch_demo_rows(sql)
            state["data_source"] = "demo"
        else:
            state["result"] = fetch_rows(sql)
            state["data_source"] = "postgres"
        state["error"] = ""
    except Exception as exc:
        state["result"] = []
        state["error"] = f"Execution failed: {exc}"
    return state


def _with_limit_safeguard(sql: str) -> str:
    """Append LIMIT 100 if the SQL doesn't already bound the result set."""
    if "limit" not in sql.lower():
        return sql.rstrip().rstrip(";") + " LIMIT 100;"
    return sql
