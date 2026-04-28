"""Disambiguation agent — resolves vague language with hardcoded defaults."""
from __future__ import annotations
import re

from backend.app.schemas.state import AgentState

AMBIGUOUS_DEFAULTS: dict[str, str] = {
    "top":    "Assume top means highest total revenue and limit 10.",
    "recent": "Assume recent means the last 30 days in the dataset by orders.order_date.",
    "best":   "Assume best means highest total revenue.",
}


def disambiguation_agent(state: AgentState) -> AgentState:
    query = state.get("query", "").strip()
    lower_query = query.lower()
    assumptions = [
        assumption
        for term, assumption in AMBIGUOUS_DEFAULTS.items()
        if re.search(rf"\b{re.escape(term)}\b", lower_query)
    ]
    refined_query = query
    if assumptions:
        refined_query = f"{query} ({' '.join(assumptions)})"
    state["is_ambiguous"] = bool(assumptions)
    state["refined_query"] = refined_query
    state["clarification"] = " ".join(assumptions)
    return state
