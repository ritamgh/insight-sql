"""PostgreSQL connection and query helpers."""
from __future__ import annotations
from contextlib import contextmanager
from typing import Any, Iterator

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ModuleNotFoundError:
    psycopg2 = None
    RealDictCursor = None

from backend.app.core.config import get_settings


@contextmanager
def get_connection() -> Iterator[Any]:
    if psycopg2 is None:
        raise RuntimeError("psycopg2 is not installed.")
    settings = get_settings()
    connection = psycopg2.connect(
        settings.database_url,
        connect_timeout=settings.database_connect_timeout_seconds,
    )
    try:
        yield connection
    finally:
        connection.close()


def explain_query(sql: str) -> list[dict[str, Any]]:
    """Run EXPLAIN (never executes) — used by validation for syntax check."""
    settings = get_settings()
    with get_connection() as connection:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("SET statement_timeout = %s", (settings.statement_timeout_ms,))
            cursor.execute(f"EXPLAIN {sql.rstrip(';')}")
            return [dict(row) for row in cursor.fetchall()]


def fetch_rows(sql: str) -> list[dict[str, Any]]:
    """Execute SQL and return rows as list of dicts."""
    settings = get_settings()
    with get_connection() as connection:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("SET statement_timeout = %s", (settings.statement_timeout_ms,))
            cursor.execute(sql)
            return [dict(row) for row in cursor.fetchall()]
