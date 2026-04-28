"""Validation agent — safety check + PostgreSQL EXPLAIN with demo fallback."""
from __future__ import annotations
import re
from typing import Any

from backend.app.db.connection import explain_query
from backend.app.db.health import friendly_database_error, is_database_connection_error
from backend.app.schemas.state import AgentState

FORBIDDEN_SQL = re.compile(
    r"\b(DROP|DELETE|UPDATE|INSERT|ALTER|TRUNCATE)\b",
    flags=re.IGNORECASE,
)


def validation_agent(state: AgentState) -> dict[str, Any]:
    sql = state.get("sql", "").strip()

    safety_error = _safety_error(sql)
    if safety_error:
        return {"is_valid": False, "error": safety_error, "retryable": False}

    try:
        explain_query(sql)
    except Exception as exc:
        if is_database_connection_error(exc):
            return {
                "is_valid": True,
                "error": "",
                "retryable": True,
                "execution_backend": "demo",
                "detail": "PostgreSQL unavailable — using demo data.",
            }
        return {
            "is_valid": False,
            "error": f"EXPLAIN failed: {exc}",
            "retryable": True,
            "execution_backend": "postgres",
        }

    return {
        "is_valid": True,
        "error": "",
        "retryable": True,
        "execution_backend": "postgres",
        "detail": "SQL passed safety checks and PostgreSQL EXPLAIN.",
    }


def _safety_error(sql: str) -> str | None:
    if not sql:
        return "SQL is empty."
    if FORBIDDEN_SQL.search(sql):
        return "SQL contains a forbidden write or DDL keyword."
    normalized = sql.rstrip().rstrip(";")
    if ";" in normalized:
        return "SQL must contain exactly one statement."
    if not re.match(r"^\s*(SELECT|WITH)\b", normalized, flags=re.IGNORECASE):
        return "Only SELECT queries are allowed."
    return None
