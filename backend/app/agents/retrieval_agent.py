"""Retrieval agent — attaches relevant schema context to state."""
from __future__ import annotations

from backend.app.db.northwind_schema import select_schema_context
from backend.app.schemas.state import AgentState


def retrieval_agent(state: AgentState) -> AgentState:
    query = state.get("refined_query") or state.get("query", "")
    state["schema"] = select_schema_context(query)
    return state
