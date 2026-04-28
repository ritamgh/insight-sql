"""Explanation agent — LLM-generated summary with deterministic fallback."""
from __future__ import annotations
from typing import Any

from backend.app.schemas.state import AgentState
from backend.app.services.llm import LLMUnavailableError, generate_explanation_with_groq


def explanation_agent(state: AgentState) -> AgentState:
    if state.get("out_of_scope"):
        state["explanation"] = (
            "This question is outside the Northwind dataset domain. "
            "Northwind can answer questions about customers, orders, products, "
            "suppliers, employees, shipping, revenue, and inventory."
        )
        return state

    if state.get("error"):
        state["explanation"] = (
            "I could not complete the analysis because the SQL pipeline reported an error. "
            f"Details: {state['error']}"
        )
        return state

    rows = state.get("result", [])
    if not rows:
        state["explanation"] = (
            "The query ran successfully but returned no rows. "
            "The selected filters may be too narrow for the current Northwind data."
        )
        if state.get("cardinality_warning"):
            state["explanation"] = f"{state['cardinality_warning']} {state['explanation']}"
        return state

    prefix = _result_prefix(rows, state.get("cardinality_warning"))
    one_cell = _single_cell_answer(rows)
    if one_cell:
        state["explanation"] = f"{prefix}{one_cell}" if prefix else one_cell
        return state

    try:
        explanation = generate_explanation_with_groq(
            query=state.get("query", ""),
            sql=state.get("sql", ""),
            rows=rows,
        )
    except LLMUnavailableError:
        explanation = _fallback_one_liner(rows)

    state["explanation"] = f"{prefix}{explanation}" if prefix else explanation

    return state


def _single_cell_answer(rows: list[dict[str, Any]]) -> str | None:
    if len(rows) == 1 and len(rows[0]) == 1:
        return f"The answer is {next(iter(rows[0].values()))}."
    return None


def _result_prefix(rows: list[dict[str, Any]], warning: str | None) -> str:
    parts: list[str] = []
    if warning:
        parts.append(warning)
    if len(rows) > 20:
        parts.append(f"Showing the top {min(len(rows), 100)} of {len(rows)} rows.")
    return " ".join(parts) + (" " if parts else "")


def _fallback_one_liner(rows: list[dict[str, Any]]) -> str:
    first_row = rows[0]
    label = next(
        (str(v) for v in first_row.values() if isinstance(v, str) and v),
        f"{list(first_row.keys())[0]} {list(first_row.values())[0]}",
    )
    return f"Returned {len(rows)} row(s). The first result is {label}."
