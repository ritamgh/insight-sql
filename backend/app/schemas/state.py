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
    clarification_question: str
    user_clarification: str
    applied_clarification: str
    clarification_attempts: int
    pending_clarification: bool
    disambiguation_triggered: bool
    retrieved_examples: list[dict[str, Any]]
    retrieved_schema_chunks: list[dict[str, Any]]
    validation_layers_triggered: list[str]
    failed_layer: str | None
    cardinality_warning: str | None
    last_sql: str
    use_rag: bool
    use_validation_layers: bool
