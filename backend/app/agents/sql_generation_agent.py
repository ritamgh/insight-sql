"""SQL generation agent — calls Groq to produce a SELECT statement."""
from __future__ import annotations

from backend.app.schemas.state import AgentState
from backend.app.services.llm import generate_sql_with_groq


def sql_generation_agent(state: AgentState) -> AgentState:
    last_error = state.get("error") if state.get("retry_count", 0) > 0 else None
    last_sql = state.get("sql") if state.get("retry_count", 0) > 0 else None
    state["last_sql"] = last_sql or ""
    state["sql"] = generate_sql_with_groq(
        refined_query=state.get("refined_query") or state.get("query", ""),
        schema_context=state.get("schema", ""),
        retrieved_examples=state.get("retrieved_examples", []),
        last_error=last_error,
        last_sql=last_sql,
    )
    return state
