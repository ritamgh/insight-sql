"""Disambiguation agent with LLM clarification and deterministic fallback."""
from __future__ import annotations
import re

from backend.app.db.northwind_schema import select_schema_context
from backend.app.schemas.state import AgentState
from backend.app.services.llm import disambiguate_with_groq

AMBIGUOUS_DEFAULTS: dict[str, str] = {
    "top":    "Assume top means highest total revenue and limit 10.",
    "recent": "Assume recent means the last 30 days in the dataset by orders.order_date.",
    "best":   "Assume best means highest total revenue.",
    "data":   "Assume the user wants recent orders with customer names.",
    "sales":  "Assume sales means total revenue by category across all available orders.",
    "show":   "Assume the user wants recent orders if no metric or entity is specified.",
}

AMBIGUOUS_QUESTIONS: dict[str, str] = {
    "recent": "What time window should I use for recent orders?",
    "sales": "How should I break down sales: by customer, product, category, employee, or time period?",
}

PRODUCT_RANKING_QUESTION = (
    "What metric should I use to determine the best products? "
    "Options from the database include total revenue, units sold, order count, "
    "current unit price, units in stock, units on order, reorder level, or discount."
)

SALES_DIMENSION_TERMS = {
    "customer",
    "customers",
    "product",
    "products",
    "category",
    "categories",
    "employee",
    "employees",
    "salesperson",
    "salespeople",
    "month",
    "monthly",
    "quarter",
    "quarterly",
    "year",
    "yearly",
    "time",
    "date",
    "country",
    "region",
}

RANKING_METRIC_TERMS = {
    "revenue",
    "sales",
    "units sold",
    "quantity",
    "quantities",
    "order count",
    "orders",
    "count",
    "unit price",
    "price",
    "stock",
    "inventory",
    "units in stock",
    "units on order",
    "reorder",
    "reorder level",
    "discount",
    "freight",
}

TIME_WINDOW_RE = re.compile(
    r"\b(?:last|past|previous)?\s*\d+\s*(?:days?|weeks?|months?|years?)\b"
    r"|\b(?:today|yesterday|this\s+week|this\s+month|this\s+year|last\s+week|last\s+month|last\s+year)\b",
    flags=re.IGNORECASE,
)


def disambiguation_agent(state: AgentState) -> AgentState:
    query = state.get("query", "").strip()
    attempts = int(state.get("clarification_attempts", 0) or 0)
    user_answer = str(state.get("user_clarification", "") or "").strip()
    clarification_question = str(state.get("clarification_question", "") or "").strip()
    query_for_llm = (
        merge_clarification(query, clarification_question, user_answer)
        if attempts > 0 and user_answer
        else query
    )

    if attempts > 0 and user_answer:
        state["pending_clarification"] = False
        state["clarification_question"] = ""
        state["clarification"] = ""
        state["is_ambiguous"] = False
        state["disambiguation_triggered"] = False
        state["refined_query"] = query_for_llm
        state["applied_clarification"] = user_answer
        return state

    decision = _llm_or_fallback(query_for_llm)
    state["pending_clarification"] = False
    state["clarification_question"] = decision.get("clarification_question", "")
    state["clarification"] = decision.get("default_assumption", "")
    state["is_ambiguous"] = bool(decision.get("is_ambiguous"))
    state["disambiguation_triggered"] = False

    if attempts > 0 and not state["is_ambiguous"]:
        state["clarification"] = ""

    if state["is_ambiguous"] and attempts < 2:
        state["pending_clarification"] = True
        state["refined_query"] = query_for_llm
        return state

    if state["is_ambiguous"]:
        assumption = state.get("clarification") or "Assume a recent orders summary."
        state["refined_query"] = f"{query_for_llm} ({assumption})"
        state["pending_clarification"] = False
        state["disambiguation_triggered"] = True
        return state

    state["refined_query"] = query_for_llm
    return state


def _llm_or_fallback(query: str) -> dict[str, str | bool]:
    fallback = _fallback_decision(query)
    schema_summary = select_schema_context(query)
    try:
        decision = disambiguate_with_groq(query, schema_summary)
    except Exception:
        return fallback
    return _normalize_decision(query, decision)


def _fallback_decision(query: str) -> dict[str, str | bool]:
    lower_query = query.lower()
    assumptions = [
        assumption
        for term, assumption in AMBIGUOUS_DEFAULTS.items()
        if re.search(rf"\b{re.escape(term)}\b", lower_query)
    ]
    clarification_terms = [
        term
        for term in AMBIGUOUS_QUESTIONS
        if re.search(rf"\b{re.escape(term)}\b", lower_query)
    ]
    if _is_broad_ambiguous(query):
        return {
            "is_ambiguous": True,
            "clarification_question": "Which Northwind entity or metric should I analyze?",
            "default_assumption": AMBIGUOUS_DEFAULTS["data"],
        }
    if _is_sales_with_dimension(query):
        return {"is_ambiguous": False, "clarification_question": "", "default_assumption": ""}
    if _is_recent_with_time_window(query):
        return {"is_ambiguous": False, "clarification_question": "", "default_assumption": ""}
    if _is_product_ranking_with_metric(query):
        return {"is_ambiguous": False, "clarification_question": "", "default_assumption": ""}
    if _is_ambiguous_product_ranking(query):
        return {
            "is_ambiguous": True,
            "clarification_question": PRODUCT_RANKING_QUESTION,
            "default_assumption": AMBIGUOUS_DEFAULTS["top"],
        }
    if clarification_terms:
        term = clarification_terms[0]
        return {
            "is_ambiguous": True,
            "clarification_question": AMBIGUOUS_QUESTIONS[term],
            "default_assumption": AMBIGUOUS_DEFAULTS[term],
        }
    if assumptions:
        return {
            "is_ambiguous": False,
            "clarification_question": "",
            "default_assumption": " ".join(assumptions),
        }
    return {"is_ambiguous": False, "clarification_question": "", "default_assumption": ""}


def _normalize_decision(query: str, decision: dict[str, str | bool]) -> dict[str, str | bool]:
    if _is_sales_with_dimension(query):
        return {"is_ambiguous": False, "clarification_question": "", "default_assumption": ""}
    if _is_recent_with_time_window(query):
        return {"is_ambiguous": False, "clarification_question": "", "default_assumption": ""}
    if _is_recent_without_time_window(query):
        return {
            "is_ambiguous": True,
            "clarification_question": AMBIGUOUS_QUESTIONS["recent"],
            "default_assumption": AMBIGUOUS_DEFAULTS["recent"],
        }
    if _is_bare_sales_or_revenue(query):
        return {
            "is_ambiguous": True,
            "clarification_question": AMBIGUOUS_QUESTIONS["sales"],
            "default_assumption": AMBIGUOUS_DEFAULTS["sales"],
        }
    if _is_product_ranking_with_metric(query):
        return {"is_ambiguous": False, "clarification_question": "", "default_assumption": ""}
    if _is_ambiguous_product_ranking(query):
        return {
            "is_ambiguous": True,
            "clarification_question": PRODUCT_RANKING_QUESTION,
            "default_assumption": AMBIGUOUS_DEFAULTS["top"],
        }
    return decision


def merge_clarification(query: str, clarification_question: str, user_answer: str) -> str:
    answer = user_answer.strip()
    if not answer:
        return query
    query = query.rstrip()
    lower_answer = answer.lower()
    lower_question = clarification_question.lower()
    time_window = _normalize_time_window_answer(answer)
    if time_window:
        return _append_once(query, f"in the {time_window}")
    if lower_answer.startswith(("by ", "per ", "for ", "with ", "in ")):
        return _append_once(query, answer)
    if re.search(r"\b(by|per|grouped by|broken down by)\b", lower_answer):
        return _append_once(query, answer)
    if _asks_for_breakdown(lower_question):
        return _append_once(query, f"by {answer}")
    if _asks_for_metric(lower_question):
        return _append_once(query, f"by {answer}")
    if _asks_for_time_window(lower_question):
        return _append_once(query, f"in the {answer}")
    if _asks_for_filter(lower_question):
        return _append_once(query, f"for {answer}")
    if _looks_like_dimension_answer(answer):
        return _append_once(query, f"by {answer}")
    if _looks_like_filter_answer(answer):
        return _append_once(query, f"for {answer}")
    return f"{query}. User clarification: {answer}."


def _append_once(query: str, addition: str) -> str:
    clean_addition = addition.strip()
    if not clean_addition:
        return query
    if query.lower().endswith(clean_addition.lower()):
        return query
    return f"{query} {clean_addition}"


def _asks_for_breakdown(question: str) -> bool:
    return bool(re.search(r"\b(break down|breakdown|group|grouped|segment|dimension|by what|by which)\b", question))


def _asks_for_metric(question: str) -> bool:
    if "entity or metric" in question:
        return False
    return bool(re.search(r"\b(metric|measure|determine|rank|ranking|best|top|highest|lowest|sort)\b", question))


def _asks_for_time_window(question: str) -> bool:
    return bool(re.search(r"\b(time window|timeframe|period|date range|how far back|recent|when)\b", question))


def _asks_for_filter(question: str) -> bool:
    return bool(re.search(r"\b(which|what)\s+(country|city|region|customer|product|category|employee|supplier|shipper)\b", question))


def _looks_like_dimension_answer(answer: str) -> bool:
    lower_answer = answer.lower()
    return any(re.fullmatch(rf"(?:the\s+)?{re.escape(term)}", lower_answer) for term in SALES_DIMENSION_TERMS)


def _looks_like_filter_answer(answer: str) -> bool:
    clean_answer = answer.strip()
    if re.search(r"\b(with|over|under|above|below|more|less|greater|fewer|where)\b", clean_answer, re.I):
        return False
    if len(clean_answer.split()) > 3:
        return False
    return bool(re.fullmatch(r"[A-Za-z][A-Za-z .'-]{1,60}", clean_answer))


def _is_bare_sales_or_revenue(query: str) -> bool:
    lower_query = query.lower()
    has_sales_metric = bool(re.search(r"\b(sales|sale|revenue)\b", lower_query))
    return has_sales_metric and not _is_sales_with_dimension(query)


def _is_sales_with_dimension(query: str) -> bool:
    lower_query = query.lower()
    has_sales_metric = bool(re.search(r"\b(sales|sale|revenue)\b", lower_query))
    if not has_sales_metric:
        return False
    return any(re.search(rf"\b{re.escape(term)}\b", lower_query) for term in SALES_DIMENSION_TERMS)


def _is_ambiguous_product_ranking(query: str) -> bool:
    lower_query = query.lower()
    has_product = bool(re.search(r"\b(products?|items?)\b", lower_query))
    has_ranking_word = bool(re.search(r"\b(best|top|highest|lowest|worst)\b", lower_query))
    return has_product and has_ranking_word and not _has_ranking_metric(query)


def _is_product_ranking_with_metric(query: str) -> bool:
    lower_query = query.lower()
    has_product = bool(re.search(r"\b(products?|items?)\b", lower_query))
    has_ranking_word = bool(re.search(r"\b(best|top|highest|lowest|worst)\b", lower_query))
    return has_product and has_ranking_word and _has_ranking_metric(query)


def _has_ranking_metric(query: str) -> bool:
    lower_query = query.lower()
    return any(re.search(rf"\b{re.escape(term)}\b", lower_query) for term in RANKING_METRIC_TERMS)


def _is_recent_with_time_window(query: str) -> bool:
    return bool(re.search(r"\brecent\b", query, flags=re.IGNORECASE) and TIME_WINDOW_RE.search(query))


def _is_recent_without_time_window(query: str) -> bool:
    return bool(re.search(r"\brecent\b", query, flags=re.IGNORECASE) and not TIME_WINDOW_RE.search(query))


def _normalize_time_window_answer(answer: str) -> str:
    lower_answer = answer.strip().lower()
    if not lower_answer:
        return ""
    if re.fullmatch(r"\d+\s*(?:days?|weeks?|months?|years?)", lower_answer):
        return f"last {lower_answer}"
    if re.fullmatch(r"(?:last|past|previous)\s+\d+\s*(?:days?|weeks?|months?|years?)", lower_answer):
        return lower_answer.replace("past ", "last ").replace("previous ", "last ")
    if lower_answer in {
        "today",
        "yesterday",
        "this week",
        "this month",
        "this year",
        "last week",
        "last month",
        "last year",
    }:
        return lower_answer
    return ""


def _is_broad_ambiguous(query: str) -> bool:
    lower_query = query.lower()
    return bool(re.fullmatch(r"\s*(show|list|get|give me)?\s*(me\s+)?(the\s+)?data\s*", lower_query))
