"""Unit tests for individual agents. No live Postgres or Groq required."""
from __future__ import annotations
import pytest

from backend.app.agents.disambiguation_agent import disambiguation_agent
from backend.app.agents.domain_guard_agent import domain_guard_agent
from backend.app.agents.execution_agent import _with_limit_safeguard, execution_agent
from backend.app.agents.explanation_agent import explanation_agent
from backend.app.agents.retrieval_agent import retrieval_agent
from backend.app.agents.sql_generation_agent import sql_generation_agent
from backend.app.agents.validation_agent import validation_agent
from backend.app.db.demo_executor import fetch_demo_rows
from backend.app.services.llm import LLMUnavailableError


# ── Disambiguation ────────────────────────────────────────────────────────────

def test_disambiguation_marks_ambiguous_and_adds_default_assumption(monkeypatch):
    monkeypatch.setattr(
        "backend.app.agents.disambiguation_agent.disambiguate_with_groq",
        lambda *_: {
            "is_ambiguous": True,
            "clarification_question": "What time window should I use for recent orders?",
            "default_assumption": "Assume recent means the last 30 days in the dataset by orders.order_date.",
        },
    )
    state = disambiguation_agent({"query": "Show recent orders"})
    assert state["pending_clarification"] is True
    assert "time window" in state["clarification_question"]
    assert "last 30 days" in state["clarification"]


# ── Retrieval ─────────────────────────────────────────────────────────────────

def test_retrieval_selects_relevant_schema_snippets():
    state = retrieval_agent({"refined_query": "Top customers by revenue"})
    assert "Table: customers" in state["schema"]
    assert "Table: orders" in state["schema"]
    assert "FOREIGN KEY RELATIONSHIPS" in state["schema"]
    assert state["retrieved_schema_chunks"]


# ── Domain guard ──────────────────────────────────────────────────────────────

def test_domain_guard_rejects_out_of_scope_query():
    state = domain_guard_agent({"query": "Highest sold car model"})
    assert state["out_of_scope"] is True
    assert "outside the Northwind domain" in state["error"]


def test_domain_guard_allows_supported_query():
    state = domain_guard_agent({"query": "Top customers by revenue"})
    assert state["out_of_scope"] is False


# ── Validation ────────────────────────────────────────────────────────────────

def test_validation_blocks_dangerous_sql():
    result = validation_agent({"sql": "DELETE FROM customers;"})
    assert result["is_valid"] is False
    assert "forbidden" in str(result["error"])
    assert result["failed_layer"] == "safety"


def test_validation_uses_explain_for_safe_sql(monkeypatch):
    calls = []

    def mock_explain(sql: str):
        calls.append(sql)
        return [{"QUERY PLAN": "Seq Scan"}]

    monkeypatch.setattr(
        "backend.app.agents.validation_agent.explain_query", mock_explain
    )
    sql = "SELECT customers.customer_id FROM customers;"
    result = validation_agent({"sql": sql})
    assert result["is_valid"] is True
    assert calls[0] == sql  # stripping happens inside connection.explain_query, not before the call


def test_validation_falls_back_to_demo_when_database_unreachable(monkeypatch):
    monkeypatch.setattr(
        "backend.app.agents.validation_agent.explain_query",
        lambda _: (_ for _ in ()).throw(RuntimeError("connection refused")),
    )
    result = validation_agent({"sql": "SELECT customers.customer_id FROM customers;"})
    assert result["is_valid"] is True
    assert result["execution_backend"] == "demo"


def test_validation_marks_real_sql_errors_retryable(monkeypatch):
    monkeypatch.setattr(
        "backend.app.agents.validation_agent.explain_query",
        lambda _: (_ for _ in ()).throw(
            RuntimeError("syntax error at or near 'SELEKT'")
        ),
    )
    result = validation_agent({"sql": "SELECT customers.customer_id FROM customers;"})
    assert result["is_valid"] is False
    assert result.get("retryable") is True


# ── Execution ─────────────────────────────────────────────────────────────────

def test_execution_adds_limit_safeguard_when_missing():
    result = _with_limit_safeguard("SELECT customers.customer_id FROM customers;")
    assert result.endswith("LIMIT 100;")


def test_execution_uses_demo_backend_when_requested():
    sql = """SELECT
    customers.customer_id,
    customers.company_name,
    SUM(order_details.unit_price * order_details.quantity * (1 - order_details.discount)) AS total_revenue
FROM customers
JOIN orders ON customers.customer_id = orders.customer_id
JOIN order_details ON orders.order_id = order_details.order_id
GROUP BY customers.customer_id, customers.company_name
ORDER BY total_revenue DESC
LIMIT 10;"""
    state = execution_agent({
        "sql": sql,
        "validation": {"execution_backend": "demo"},
    })
    assert state["data_source"] == "demo"
    assert len(state["result"]) > 0


def test_demo_recent_orders_honors_dataset_relative_interval():
    one_year_sql = """
SELECT orders.order_id, orders.customer_id, orders.order_date
FROM orders
WHERE orders.order_date >= (SELECT MAX(orders.order_date) FROM orders) - INTERVAL '1 year'
ORDER BY orders.order_date DESC
LIMIT 100;
"""
    thirty_day_sql = """
SELECT orders.order_id, orders.customer_id, orders.order_date
FROM orders
WHERE orders.order_date >= (SELECT MAX(orders.order_date) FROM orders) - INTERVAL '30 days'
ORDER BY orders.order_date DESC
LIMIT 100;
"""
    one_year_rows = fetch_demo_rows(one_year_sql)
    thirty_day_rows = fetch_demo_rows(thirty_day_sql)
    assert len(one_year_rows) > len(thirty_day_rows)
    assert len(one_year_rows) == 8


# ── SQL generation ────────────────────────────────────────────────────────────

def test_sql_generation_calls_groq(monkeypatch):
    canned_sql = "SELECT customers.customer_id FROM customers LIMIT 10;"
    monkeypatch.setattr(
        "backend.app.agents.sql_generation_agent.generate_sql_with_groq",
        lambda **_: canned_sql,
    )
    state = sql_generation_agent({
        "query": "Top customers",
        "refined_query": "Top customers",
        "schema": "Table: customers",
        "retry_count": 0,
    })
    assert state["sql"] == canned_sql


def test_sql_generation_propagates_llm_unavailable(monkeypatch):
    def raise_unavailable(**_):
        raise LLMUnavailableError("GROQ_API_KEY is not set.")

    monkeypatch.setattr(
        "backend.app.agents.sql_generation_agent.generate_sql_with_groq",
        raise_unavailable,
    )
    with pytest.raises(LLMUnavailableError):
        sql_generation_agent({
            "query": "Top customers",
            "refined_query": "Top customers",
            "schema": "Table: customers",
            "retry_count": 0,
        })


# ── Explanation ───────────────────────────────────────────────────────────────

def test_explanation_uses_groq_when_rows_present(monkeypatch):
    monkeypatch.setattr(
        "backend.app.agents.explanation_agent.generate_explanation_with_groq",
        lambda **_: "Top customer is Ernst Handel.",
    )
    state = explanation_agent({
        "query": "Top customers",
        "sql": "SELECT ...",
        "result": [{"customer_id": "ERNSH", "company_name": "Ernst Handel", "total_revenue": 4200.0}],
    })
    assert state["explanation"] == "Top customer is Ernst Handel."


def test_explanation_falls_back_when_groq_fails(monkeypatch):
    def raise_unavailable(**_):
        raise LLMUnavailableError("no key")

    monkeypatch.setattr(
        "backend.app.agents.explanation_agent.generate_explanation_with_groq",
        raise_unavailable,
    )
    state = explanation_agent({
        "query": "Top customers",
        "sql": "SELECT ...",
        "result": [{"customer_id": "ERNSH", "company_name": "Ernst Handel"}],
    })
    assert state["explanation"]
    assert "Ernst Handel" in state["explanation"] or "1 row" in state["explanation"]
