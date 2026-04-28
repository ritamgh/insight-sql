"""Tests for validation layers."""
from __future__ import annotations

from backend.app.agents.validation_agent import validation_agent


def test_safety_blocks_forbidden_statements():
    for sql in ("INSERT INTO customers VALUES ('x')", "DROP TABLE customers", "COPY customers TO STDOUT"):
        result = validation_agent({"sql": sql})
        assert result["is_valid"] is False
        assert result["failed_layer"] == "safety"


def test_safety_allows_forbidden_words_inside_string_literals(monkeypatch):
    monkeypatch.setattr("backend.app.agents.validation_agent.explain_query", lambda _: [])
    result = validation_agent({"sql": "SELECT 'DROP shipment' AS note FROM orders;"})
    assert result["is_valid"] is True


def test_schema_rejects_unknown_column(monkeypatch):
    monkeypatch.setattr("backend.app.agents.validation_agent.explain_query", lambda _: [])
    result = validation_agent({"sql": "SELECT customers.bogus_col FROM customers;"})
    assert result["is_valid"] is False
    assert result["failed_layer"] == "schema"


def test_schema_allows_order_by_select_alias(monkeypatch):
    monkeypatch.setattr("backend.app.agents.validation_agent.explain_query", lambda _: [])
    sql = """
SELECT
    employees.employee_id,
    employees.first_name,
    employees.last_name,
    SUM(order_details.unit_price * order_details.quantity * (1 - order_details.discount)) AS total_revenue
FROM employees
JOIN orders ON employees.employee_id = orders.employee_id
JOIN order_details ON orders.order_id = order_details.order_id
GROUP BY employees.employee_id, employees.first_name, employees.last_name
ORDER BY total_revenue DESC;
"""
    result = validation_agent({"sql": sql})
    assert result["is_valid"] is True


def test_semantic_rejects_implicit_join(monkeypatch):
    monkeypatch.setattr("backend.app.agents.validation_agent.explain_query", lambda _: [])
    result = validation_agent({"sql": "SELECT customers.customer_id, orders.order_id FROM customers, orders;"})
    assert result["is_valid"] is False
    assert result["failed_layer"] in {"semantic", "schema"}


def test_semantic_still_runs_before_demo_fallback(monkeypatch):
    monkeypatch.setattr(
        "backend.app.agents.validation_agent.explain_query",
        lambda _: (_ for _ in ()).throw(RuntimeError("connection refused")),
    )
    result = validation_agent({"sql": "SELECT customers.customer_id, orders.order_id FROM customers, orders;"})
    assert result["is_valid"] is False
    assert result["failed_layer"] == "semantic"


def test_explain_connection_fallback_uses_demo(monkeypatch):
    monkeypatch.setattr(
        "backend.app.agents.validation_agent.explain_query",
        lambda _: (_ for _ in ()).throw(RuntimeError("connection refused")),
    )
    result = validation_agent({"sql": "SELECT customers.customer_id FROM customers;"})
    assert result["is_valid"] is True
    assert result["execution_backend"] == "demo"
