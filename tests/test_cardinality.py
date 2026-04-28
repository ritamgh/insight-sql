"""Tests for execution cardinality behavior."""
from __future__ import annotations

from backend.app.agents.execution_agent import _has_limit, execution_agent


def test_limit_detected_without_string_false_positive():
    assert _has_limit("SELECT * FROM customers LIMIT 5;") is True
    assert _has_limit("SELECT 'limit' AS label FROM customers;") is False


def test_cardinality_warning_for_large_non_aggregate(monkeypatch):
    monkeypatch.setattr(
        "backend.app.agents.execution_agent.fetch_rows",
        lambda _: [{"customer_id": str(idx)} for idx in range(100)],
    )
    state = execution_agent({"sql": "SELECT customers.customer_id FROM customers;", "validation": {}})
    assert state["cardinality_warning"]


def test_no_cardinality_warning_for_aggregate(monkeypatch):
    monkeypatch.setattr(
        "backend.app.agents.execution_agent.fetch_rows",
        lambda _: [{"count": 100}],
    )
    state = execution_agent({"sql": "SELECT COUNT(*) AS count FROM customers;", "validation": {}})
    assert state["cardinality_warning"] is None
