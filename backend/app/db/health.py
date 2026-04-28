"""Database health check and user-facing error messages."""
from __future__ import annotations
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from backend.app.core.config import get_settings
from backend.app.db.connection import get_connection


def check_database_health() -> dict[str, Any]:
    settings = get_settings()
    try:
        with get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1;")
                cursor.fetchone()
    except Exception as exc:
        return {
            "is_connected": False,
            "database_url": mask_database_url(settings.database_url),
            "message": friendly_database_error(exc),
            "hint": (
                "PostgreSQL is optional. The app falls back to built-in demo data, "
                "or run: docker compose up -d"
            ),
        }
    return {
        "is_connected": True,
        "database_url": mask_database_url(settings.database_url),
        "message": "Connected to PostgreSQL.",
        "hint": "",
    }


def mask_database_url(database_url: str) -> str:
    parts = urlsplit(database_url)
    if not parts.password:
        return database_url
    username = parts.username or ""
    hostname = parts.hostname or ""
    port = f":{parts.port}" if parts.port else ""
    netloc = f"{username}:***@{hostname}{port}"
    return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))


def friendly_database_error(exc: Exception) -> str:
    message = str(exc).strip()
    lower = message.lower()
    if "connection refused" in lower:
        return "PostgreSQL refused the connection on localhost:5432. The server is not running."
    if "timeout expired" in lower or "timed out" in lower:
        return "The database connection timed out."
    if "password authentication failed" in lower:
        return "PostgreSQL rejected the username or password in DATABASE_URL."
    if "database" in lower and "does not exist" in lower:
        return "The configured PostgreSQL database does not exist."
    return message


def is_database_connection_error(exc: Exception) -> bool:
    lower = str(exc).lower()
    return any(
        fragment in lower
        for fragment in (
            "connection refused",
            "could not connect",
            "timeout expired",
            "timed out",
            "password authentication failed",
            "does not exist",
        )
    )
