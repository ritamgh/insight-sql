"""Integration tests for the LangGraph controller. No live Postgres or Groq."""
from __future__ import annotations
import pytest

from backend.app.controller import run_agent_pipeline
from backend.app.schemas.state import AgentState


def _agent_names(state: AgentState) -> list[str]:
    return [row["agent"] for row in state.get("agent_trace", [])]


# ── Retry on validation error ─────────────────────────────────────────────────

def test_controller_retries_after_validation_error(monkeypatch):
    call_count = {"sql_gen": 0, "validation": 0}

    def mock_sql_agent(state):
        call_count["sql_gen"] += 1
        state["sql"] = (
            "INVALID SQL"
            if call_count["sql_gen"] == 1
            else "SELECT customers.customer_id FROM customers LIMIT 1;"
        )
        return state

    def mock_validation_agent(state):
        call_count["validation"] += 1
        if call_count["validation"] == 1:
            return {"is_valid": False, "error": "syntax error", "retryable": True}
        return {
            "is_valid": True,
            "error": "",
            "retryable": True,
            "execution_backend": "demo",
            "detail": "ok",
        }

    def mock_execution_agent(state):
        state["result"] = [{"customer_id": "ALFKI"}]
        state["data_source"] = "demo"
        state["error"] = ""
        return state

    def mock_explanation_agent(state):
        state["explanation"] = "All good."
        return state

    def mock_disambiguation_agent(state):
        state["refined_query"] = state["query"]
        state["pending_clarification"] = False
        state["is_ambiguous"] = False
        return state

    monkeypatch.setattr("backend.app.controller.disambiguation_agent", mock_disambiguation_agent)
    monkeypatch.setattr("backend.app.controller.sql_generation_agent", mock_sql_agent)
    monkeypatch.setattr("backend.app.controller.validation_agent", mock_validation_agent)
    monkeypatch.setattr("backend.app.controller.execution_agent", mock_execution_agent)
    monkeypatch.setattr("backend.app.controller.explanation_agent", mock_explanation_agent)

    # Clear lru_cache so the patched agents are picked up
    from backend.app.controller import _build_workflow
    _build_workflow.cache_clear()

    state = run_agent_pipeline("Top customers")

    assert state["retry_count"] == 1
    assert state["result"] == [{"customer_id": "ALFKI"}]
    names = _agent_names(state)
    assert names == [
        "Disambiguation Agent",
        "Domain Guard Agent",
        "Retrieval Agent",
        "SQL Generation Agent",
        "Validation Agent",
        "SQL Generation Agent",
        "Validation Agent",
        "Execution Agent",
        "Explanation Agent",
    ]


# ── No retry on non-retryable error ──────────────────────────────────────────

def test_controller_does_not_retry_database_connection_errors(monkeypatch):
    execution_called = {"flag": False}

    def mock_sql_agent(state):
        state["sql"] = "SELECT 1;"
        return state

    def mock_validation_agent(state):
        return {
            "is_valid": False,
            "error": "PostgreSQL refused the connection on localhost:5432.",
            "retryable": False,
        }

    def mock_execution_agent(state):
        execution_called["flag"] = True
        return state

    def mock_explanation_agent(state):
        state["explanation"] = "error."
        return state

    def mock_disambiguation_agent(state):
        state["refined_query"] = state["query"]
        state["pending_clarification"] = False
        state["is_ambiguous"] = False
        return state

    monkeypatch.setattr("backend.app.controller.disambiguation_agent", mock_disambiguation_agent)
    monkeypatch.setattr("backend.app.controller.sql_generation_agent", mock_sql_agent)
    monkeypatch.setattr("backend.app.controller.validation_agent", mock_validation_agent)
    monkeypatch.setattr("backend.app.controller.execution_agent", mock_execution_agent)
    monkeypatch.setattr("backend.app.controller.explanation_agent", mock_explanation_agent)

    from backend.app.controller import _build_workflow
    _build_workflow.cache_clear()

    state = run_agent_pipeline("Top customers")

    assert state["retry_count"] == 0
    assert state["result"] == [] or state.get("result") is None or state.get("result") == []
    assert "PostgreSQL refused" in state["error"]
    assert execution_called["flag"] is False


# ── Out-of-scope early exit ───────────────────────────────────────────────────

def test_controller_stops_on_out_of_scope_query(monkeypatch):
    def mock_disambiguation_agent(state):
        state["refined_query"] = state["query"]
        state["pending_clarification"] = False
        state["is_ambiguous"] = False
        return state

    monkeypatch.setattr("backend.app.controller.disambiguation_agent", mock_disambiguation_agent)

    from backend.app.controller import _build_workflow
    _build_workflow.cache_clear()

    state = run_agent_pipeline("Highest sold car model")

    assert state["out_of_scope"] is True
    assert state.get("sql", "") == ""
    names = _agent_names(state)
    assert names == ["Disambiguation Agent", "Domain Guard Agent", "Explanation Agent"]


# ── Demo backend execution ────────────────────────────────────────────────────

def test_controller_executes_with_demo_backend_when_validation_allows_it(monkeypatch):
    def mock_sql_agent(state):
        state["sql"] = """SELECT
    customers.customer_id,
    customers.company_name,
    SUM(order_details.unit_price * order_details.quantity * (1 - order_details.discount)) AS total_revenue
FROM customers
JOIN orders ON customers.customer_id = orders.customer_id
JOIN order_details ON orders.order_id = order_details.order_id
GROUP BY customers.customer_id, customers.company_name
ORDER BY total_revenue DESC
LIMIT 10;"""
        return state

    def mock_validation_agent(state):
        return {
            "is_valid": True,
            "error": "",
            "retryable": True,
            "execution_backend": "demo",
            "detail": "demo mode",
        }

    def mock_explanation_agent(state):
        state["explanation"] = "Demo result."
        return state

    def mock_disambiguation_agent(state):
        state["refined_query"] = state["query"]
        state["pending_clarification"] = False
        state["is_ambiguous"] = False
        return state

    monkeypatch.setattr("backend.app.controller.disambiguation_agent", mock_disambiguation_agent)
    monkeypatch.setattr("backend.app.controller.sql_generation_agent", mock_sql_agent)
    monkeypatch.setattr("backend.app.controller.validation_agent", mock_validation_agent)
    monkeypatch.setattr("backend.app.controller.explanation_agent", mock_explanation_agent)

    from backend.app.controller import _build_workflow
    _build_workflow.cache_clear()

    state = run_agent_pipeline("Top customers by revenue")

    assert state["result"] == [{"customer_id": "ALFKI"}] or len(state["result"]) > 0
    assert state["data_source"] == "demo"


def test_controller_initial_state_includes_new_keys(monkeypatch):
    def mock_disambiguation_agent(state):
        state["pending_clarification"] = True
        state["clarification_question"] = "Which metric?"
        return state

    monkeypatch.setattr("backend.app.controller.disambiguation_agent", mock_disambiguation_agent)

    from backend.app.controller import _build_workflow
    _build_workflow.cache_clear()

    state = run_agent_pipeline("Show me the data")

    assert state["pending_clarification"] is True
    assert state["clarification_question"] == "Which metric?"
    assert "retrieved_examples" in state
    assert _agent_names(state) == ["Disambiguation Agent"]
