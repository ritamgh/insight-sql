"""Execution agent — runs validated SQL against Postgres or demo backend."""
from __future__ import annotations
import re

try:
    import sqlglot
    from sqlglot import exp
except ModuleNotFoundError:
    sqlglot = None
    exp = None

from backend.app.db.connection import fetch_rows
from backend.app.db.demo_executor import fetch_demo_rows
from backend.app.schemas.state import AgentState


def execution_agent(state: AgentState) -> AgentState:
    sql = _with_limit_safeguard(state.get("sql", ""))
    state["sql"] = sql
    execution_backend = (
        state.get("validation", {}).get("execution_backend")
        if isinstance(state.get("validation"), dict)
        else None
    )
    try:
        if execution_backend == "demo":
            state["result"] = fetch_demo_rows(sql)
            state["data_source"] = "demo"
        else:
            state["result"] = fetch_rows(sql)
            state["data_source"] = "postgres"
        if _should_warn_cardinality(sql, state.get("result", [])):
            state["cardinality_warning"] = (
                "Result was truncated at 100 rows. Consider adding an aggregation "
                "(SUM, COUNT, AVG) or a more specific filter to narrow the result."
            )
        else:
            state["cardinality_warning"] = None
        state["error"] = ""
    except Exception as exc:
        state["result"] = []
        state["error"] = f"Execution failed: {exc}"
    return state


def _with_limit_safeguard(sql: str) -> str:
    """Append LIMIT 100 if the SQL doesn't already bound the result set."""
    if not _has_limit(sql):
        return sql.rstrip().rstrip(";") + " LIMIT 100;"
    return sql


def _has_limit(sql: str) -> bool:
    if sqlglot is not None:
        try:
            parsed = sqlglot.parse_one(sql, read="postgres")
            return parsed.find(exp.Limit) is not None
        except Exception:
            pass
    stripped = re.sub(r"'(?:''|[^'])*'", "''", sql)
    return bool(re.search(r"\blimit\b", stripped, flags=re.IGNORECASE))


def _should_warn_cardinality(sql: str, rows: list[dict]) -> bool:
    return len(rows) >= 100 and not _has_aggregate_projection(sql)


def _has_aggregate_projection(sql: str) -> bool:
    if sqlglot is not None:
        try:
            parsed = sqlglot.parse_one(sql, read="postgres")
            aggregate_types = (exp.Sum, exp.Count, exp.Avg, exp.Min, exp.Max)
            return any(parsed.find(aggregate) for aggregate in aggregate_types)
        except Exception:
            pass
    lower_sql = sql.lower()
    return any(f"{fn}(" in lower_sql for fn in ("sum", "count", "avg", "min", "max"))
