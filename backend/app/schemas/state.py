"""Shared pipeline state passed between agents."""
from __future__ import annotations
from typing import Any, TypedDict


class AgentState(TypedDict, total=False):
    query: str
    refined_query: str
    is_ambiguous: bool
    clarification: str
    out_of_scope: bool
    schema: str
    sql: str
    validation: dict[str, Any]
    retry_count: int
    max_attempts: int
    result: list[dict[str, Any]]
    explanation: str
    error: str
    data_source: str
    agent_trace: list[dict[str, Any]]
    db_health: dict[str, Any]
