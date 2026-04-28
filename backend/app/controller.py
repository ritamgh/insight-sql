"""Central AgentOps-style controller powered by LangGraph."""
from __future__ import annotations
from functools import lru_cache
from time import perf_counter
from typing import Any

from langgraph.graph import END, START, StateGraph
from langsmith import traceable

from backend.app.agents.disambiguation_agent import disambiguation_agent
from backend.app.agents.domain_guard_agent import domain_guard_agent
from backend.app.agents.execution_agent import execution_agent
from backend.app.agents.explanation_agent import explanation_agent
from backend.app.agents.retrieval_agent import retrieval_agent
from backend.app.agents.sql_generation_agent import sql_generation_agent
from backend.app.agents.validation_agent import validation_agent
from backend.app.schemas.state import AgentState
from backend.app.services.llm import LLMUnavailableError


def initial_state(query: str) -> AgentState:
    return {
        "query": query,
        "refined_query": "",
        "schema": "",
        "sql": "",
        "result": [],
        "error": "",
        "retry_count": 0,
        "max_attempts": 2,
        "agent_trace": [],
    }


def run_agent_pipeline(query: str, max_attempts: int = 2) -> AgentState:
    state = initial_state(query)
    state["max_attempts"] = max_attempts
    graph = _build_workflow()
    return graph.invoke(state)


@lru_cache(maxsize=1)
def _build_workflow():
    workflow = StateGraph(AgentState)

    workflow.add_node("disambiguation", _disambiguation_node)
    workflow.add_node("domain_guard",   _domain_guard_node)
    workflow.add_node("retrieval",      _retrieval_node)
    workflow.add_node("sql_generation", _sql_generation_node)
    workflow.add_node("validation",     _validation_node)
    workflow.add_node("execution",      _execution_node)
    workflow.add_node("explanation",    _explanation_node)

    workflow.add_edge(START, "disambiguation")
    workflow.add_edge("disambiguation", "domain_guard")
    workflow.add_edge("retrieval", "sql_generation")
    workflow.add_edge("sql_generation", "validation")
    workflow.add_edge("execution", "explanation")
    workflow.add_edge("explanation", END)

    workflow.add_conditional_edges(
        "domain_guard",
        _route_after_domain_guard,
        {"retrieval": "retrieval", "explanation": "explanation"},
    )
    workflow.add_conditional_edges(
        "validation",
        _route_after_validation,
        {
            "sql_generation": "sql_generation",
            "execution":      "execution",
            "explanation":    "explanation",
        },
    )

    return workflow.compile()


# ── Routing functions ─────────────────────────────────────────────────────────

def _route_after_domain_guard(state: AgentState) -> str:
    if state.get("out_of_scope"):
        return "explanation"
    return "retrieval"


def _route_after_validation(state: AgentState) -> str:
    validation = state.get("validation", {})
    if validation.get("is_valid"):
        return "execution"
    can_retry = (
        validation.get("retryable", True)
        and state.get("retry_count", 0) < state.get("max_attempts", 2)
    )
    if can_retry:
        return "sql_generation"
    return "explanation"


# ── Node wrappers ─────────────────────────────────────────────────────────────

@traceable(name="Disambiguation Agent", run_type="chain")
def _disambiguation_node(state: AgentState) -> dict[str, Any]:
    started_at = perf_counter()
    updated = disambiguation_agent(dict(state))
    detail = (
        "Added default assumptions."
        if updated.get("is_ambiguous")
        else "Query was clear enough to continue."
    )
    return _state_update(
        current_state=state,
        updated_state=updated,
        keys=["is_ambiguous", "refined_query", "clarification"],
        agent="Disambiguation Agent",
        status="success",
        detail=detail,
        duration_ms=round((perf_counter() - started_at) * 1000, 2),
    )


@traceable(name="Domain Guard Agent", run_type="chain")
def _domain_guard_node(state: AgentState) -> dict[str, Any]:
    started_at = perf_counter()
    updated = domain_guard_agent(dict(state))
    detail = (
        str(updated.get("error"))
        if updated.get("out_of_scope")
        else "Question is within the Northwind domain."
    )
    return _state_update(
        current_state=state,
        updated_state=updated,
        keys=["out_of_scope", "error"],
        agent="Domain Guard Agent",
        status="success",
        detail=detail,
        duration_ms=round((perf_counter() - started_at) * 1000, 2),
    )


@traceable(name="Retrieval Agent", run_type="chain")
def _retrieval_node(state: AgentState) -> dict[str, Any]:
    started_at = perf_counter()
    updated = retrieval_agent(dict(state))
    detail = f"Selected {updated.get('schema', '').count('Table:')} schema table(s)."
    return _state_update(
        current_state=state,
        updated_state=updated,
        keys=["schema"],
        agent="Retrieval Agent",
        status="success",
        detail=detail,
        duration_ms=round((perf_counter() - started_at) * 1000, 2),
    )


@traceable(name="SQL Generation Agent", run_type="llm")
def _sql_generation_node(state: AgentState) -> dict[str, Any]:
    started_at = perf_counter()
    try:
        updated = sql_generation_agent(dict(state))
        status = "success"
        detail = "Generated SQL via Groq."
    except LLMUnavailableError as exc:
        updated = {**dict(state), "sql": "", "error": str(exc)}
        status = "failed"
        detail = str(exc)
    return _state_update(
        current_state=state,
        updated_state=updated,
        keys=["sql", "error"],
        agent="SQL Generation Agent",
        status=status,
        detail=detail,
        duration_ms=round((perf_counter() - started_at) * 1000, 2),
    )


@traceable(name="Validation Agent", run_type="chain")
def _validation_node(state: AgentState) -> dict[str, Any]:
    started_at = perf_counter()
    validation = validation_agent(dict(state))
    duration_ms = round((perf_counter() - started_at) * 1000, 2)

    updates: dict[str, Any] = {
        "validation": validation,
        "error": "" if validation["is_valid"] else str(validation["error"]),
    }

    should_retry = (
        not validation["is_valid"]
        and validation.get("retryable", True)
        and state.get("retry_count", 0) < state.get("max_attempts", 2)
    )
    if should_retry:
        updates["retry_count"] = state.get("retry_count", 0) + 1

    updates["agent_trace"] = list(state.get("agent_trace", [])) + [
        _trace_item(
            agent="Validation Agent",
            status="success" if validation["is_valid"] else "failed",
            detail=str(validation.get("detail") or updates["error"] or "Validation succeeded."),
            duration_ms=duration_ms,
        )
    ]
    return updates


@traceable(name="Execution Agent", run_type="tool")
def _execution_node(state: AgentState) -> dict[str, Any]:
    started_at = perf_counter()
    updated = execution_agent(dict(state))
    detail = (
        f"Returned {len(updated.get('result', []))} row(s)."
        if not updated.get("error")
        else str(updated["error"])
    )
    return _state_update(
        current_state=state,
        updated_state=updated,
        keys=["sql", "result", "error", "data_source"],
        agent="Execution Agent",
        status="success" if not updated.get("error") else "failed",
        detail=detail,
        duration_ms=round((perf_counter() - started_at) * 1000, 2),
    )


@traceable(name="Explanation Agent", run_type="llm")
def _explanation_node(state: AgentState) -> dict[str, Any]:
    started_at = perf_counter()
    updated = explanation_agent(dict(state))
    detail = (
        "Explained that the question is out of scope for Northwind."
        if updated.get("out_of_scope")
        else "Explained why the pipeline could not finish."
        if updated.get("error")
        else "Generated an LLM-based business summary."
    )
    return _state_update(
        current_state=state,
        updated_state=updated,
        keys=["explanation"],
        agent="Explanation Agent",
        status="success",
        detail=detail,
        duration_ms=round((perf_counter() - started_at) * 1000, 2),
    )


# ── Helpers ───────────────────────────────────────────────────────────────────

def _state_update(
    current_state: AgentState,
    updated_state: AgentState,
    keys: list[str],
    agent: str,
    status: str,
    detail: str,
    duration_ms: float,
) -> dict[str, Any]:
    updates = {key: updated_state.get(key) for key in keys}
    updates["agent_trace"] = list(current_state.get("agent_trace", [])) + [
        _trace_item(agent, status, detail, duration_ms)
    ]
    return updates


def _trace_item(
    agent: str, status: str, detail: str, duration_ms: float
) -> dict[str, Any]:
    return {"agent": agent, "status": status, "detail": detail, "duration_ms": duration_ms}
