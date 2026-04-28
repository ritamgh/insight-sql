"""Tests for pause-and-resume disambiguation."""
from __future__ import annotations

from backend.app.agents.disambiguation_agent import disambiguation_agent


def test_ambiguous_query_sets_pending_clarification(monkeypatch):
    monkeypatch.setattr(
        "backend.app.agents.disambiguation_agent.disambiguate_with_groq",
        lambda *_: {
            "is_ambiguous": True,
            "clarification_question": "Which metric?",
            "default_assumption": "Use revenue.",
        },
    )
    state = disambiguation_agent({"query": "Show me the data", "clarification_attempts": 0})
    assert state["pending_clarification"] is True
    assert state["clarification_question"] == "Which metric?"


def test_resume_combines_clarification(monkeypatch):
    monkeypatch.setattr(
        "backend.app.agents.disambiguation_agent.disambiguate_with_groq",
        lambda *_: (_ for _ in ()).throw(AssertionError("LLM should not run for user clarification")),
    )
    state = disambiguation_agent({
        "query": "Show me the data",
        "clarification_attempts": 1,
        "user_clarification": "by category",
    })
    assert state["pending_clarification"] is False
    assert state["refined_query"] == "Show me the data by category"


def test_cap_two_applies_default_assumption(monkeypatch):
    monkeypatch.setattr(
        "backend.app.agents.disambiguation_agent.disambiguate_with_groq",
        lambda *_: {
            "is_ambiguous": True,
            "clarification_question": "Which metric?",
            "default_assumption": "Use recent orders.",
        },
    )
    state = disambiguation_agent({
        "query": "Show me the data",
        "clarification_attempts": 2,
        "user_clarification": "",
    })
    assert state["pending_clarification"] is False
    assert state["disambiguation_triggered"] is True
    assert "Use recent orders." in state["refined_query"]


def test_bare_sales_requires_clarification(monkeypatch):
    monkeypatch.setattr(
        "backend.app.agents.disambiguation_agent.disambiguate_with_groq",
        lambda *_: {
            "is_ambiguous": True,
            "clarification_question": "How should I break down sales: by customer, product, category, employee, or time period?",
            "default_assumption": "Assume sales means total revenue by category across all available orders.",
        },
    )
    state = disambiguation_agent({"query": "sales", "clarification_attempts": 0})
    assert state["pending_clarification"] is True
    assert "break down sales" in state["clarification_question"]
    assert "total revenue by category" in state["clarification"]


def test_sales_by_customer_is_clear_even_if_llm_says_ambiguous(monkeypatch):
    monkeypatch.setattr(
        "backend.app.agents.disambiguation_agent.disambiguate_with_groq",
        lambda *_: {
            "is_ambiguous": True,
            "clarification_question": "How should I break down sales?",
            "default_assumption": "Assume sales by category.",
        },
    )
    state = disambiguation_agent({"query": "sales by customer", "clarification_attempts": 0})
    assert state["pending_clarification"] is False
    assert state["is_ambiguous"] is False
    assert state["refined_query"] == "sales by customer"


def test_sales_resume_by_customer_combines_to_clear_query(monkeypatch):
    monkeypatch.setattr(
        "backend.app.agents.disambiguation_agent.disambiguate_with_groq",
        lambda *_: (_ for _ in ()).throw(AssertionError("LLM should not run for user clarification")),
    )
    state = disambiguation_agent({
        "query": "sales",
        "clarification_question": "How should I break down sales: by customer, product, category, employee, or time period?",
        "clarification_attempts": 1,
        "user_clarification": "customer",
    })
    assert state["pending_clarification"] is False
    assert state["is_ambiguous"] is False
    assert state["refined_query"] == "sales by customer"


def test_best_products_question_includes_database_metric_options(monkeypatch):
    monkeypatch.setattr(
        "backend.app.agents.disambiguation_agent.disambiguate_with_groq",
        lambda *_: {
            "is_ambiguous": False,
            "clarification_question": "",
            "default_assumption": "",
        },
    )
    state = disambiguation_agent({"query": "best products", "clarification_attempts": 0})
    assert state["pending_clarification"] is True
    assert "Options from the database include" in state["clarification_question"]
    assert "total revenue" in state["clarification_question"]
    assert "units sold" in state["clarification_question"]
    assert "units in stock" in state["clarification_question"]
    assert "discount" in state["clarification_question"]


def test_best_products_with_metric_is_clear(monkeypatch):
    monkeypatch.setattr(
        "backend.app.agents.disambiguation_agent.disambiguate_with_groq",
        lambda *_: {
            "is_ambiguous": True,
            "clarification_question": "What metric?",
            "default_assumption": "Use revenue.",
        },
    )
    state = disambiguation_agent({"query": "best products by revenue", "clarification_attempts": 0})
    assert state["pending_clarification"] is False
    assert state["is_ambiguous"] is False
    assert state["refined_query"] == "best products by revenue"


def test_best_products_resume_order_count_becomes_clear_query(monkeypatch):
    monkeypatch.setattr(
        "backend.app.agents.disambiguation_agent.disambiguate_with_groq",
        lambda *_: (_ for _ in ()).throw(AssertionError("LLM should not run for user clarification")),
    )
    state = disambiguation_agent({
        "query": "Best products",
        "clarification_question": "What metric should I use to determine the best products?",
        "clarification_attempts": 1,
        "user_clarification": "order count",
    })
    assert state["pending_clarification"] is False
    assert state["is_ambiguous"] is False
    assert state["clarification"] == ""
    assert state["refined_query"] == "Best products by order count"


def test_best_products_resume_discount_becomes_clear_query(monkeypatch):
    monkeypatch.setattr(
        "backend.app.agents.disambiguation_agent.disambiguate_with_groq",
        lambda *_: (_ for _ in ()).throw(AssertionError("LLM should not run for user clarification")),
    )
    state = disambiguation_agent({
        "query": "Best products",
        "clarification_question": "What metric should I use to determine the best products?",
        "clarification_attempts": 1,
        "user_clarification": "discount",
        "clarification": "Assume top means highest total revenue and limit 10.",
    })
    assert state["pending_clarification"] is False
    assert state["is_ambiguous"] is False
    assert state["clarification"] == ""
    assert state["clarification_question"] == ""
    assert state["refined_query"] == "Best products by discount"


def test_filter_followup_combines_with_for_clause(monkeypatch):
    monkeypatch.setattr(
        "backend.app.agents.disambiguation_agent.disambiguate_with_groq",
        lambda *_: (_ for _ in ()).throw(AssertionError("LLM should not run for user clarification")),
    )
    state = disambiguation_agent({
        "query": "customers",
        "clarification_question": "Which country should I filter customers by?",
        "clarification_attempts": 1,
        "user_clarification": "Germany",
    })
    assert state["refined_query"] == "customers for Germany"
    assert state["clarification"] == ""


def test_freeform_followup_is_preserved_as_user_clarification(monkeypatch):
    monkeypatch.setattr(
        "backend.app.agents.disambiguation_agent.disambiguate_with_groq",
        lambda *_: (_ for _ in ()).throw(AssertionError("LLM should not run for user clarification")),
    )
    state = disambiguation_agent({
        "query": "Show me the data",
        "clarification_question": "Which Northwind entity or metric should I analyze?",
        "clarification_attempts": 1,
        "user_clarification": "orders with freight over 50",
    })
    assert state["refined_query"] == "Show me the data. User clarification: orders with freight over 50."
    assert state["clarification"] == ""


def test_recent_orders_resume_with_one_year_becomes_clear_query(monkeypatch):
    monkeypatch.setattr(
        "backend.app.agents.disambiguation_agent.disambiguate_with_groq",
        lambda *_: (_ for _ in ()).throw(AssertionError("LLM should not run for user clarification")),
    )
    state = disambiguation_agent({
        "query": "recent orders",
        "clarification_question": "What time window should I use for recent orders?",
        "clarification_attempts": 1,
        "user_clarification": "1 year",
    })
    assert state["pending_clarification"] is False
    assert state["is_ambiguous"] is False
    assert state["refined_query"] == "recent orders in the last 1 year"


def test_recent_orders_without_time_window_still_requires_clarification(monkeypatch):
    monkeypatch.setattr(
        "backend.app.agents.disambiguation_agent.disambiguate_with_groq",
        lambda *_: {
            "is_ambiguous": False,
            "clarification_question": "",
            "default_assumption": "",
        },
    )
    state = disambiguation_agent({"query": "recent orders", "clarification_attempts": 0})
    assert state["pending_clarification"] is True
    assert "time window" in state["clarification_question"]
