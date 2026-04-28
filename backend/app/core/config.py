"""Runtime configuration for InsightSQL."""
from __future__ import annotations
import os
from dataclasses import dataclass, field
from pathlib import Path


def _load_env_file() -> None:
    env_file = Path(__file__).resolve().parents[3] / ".env"
    if not env_file.exists():
        return
    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_env_file()


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default)


def _env_int(name: str, default: str) -> int:
    return int(os.getenv(name, default))


@dataclass(frozen=True)
class Settings:
    database_url: str = field(
        default_factory=lambda: _env(
            "DATABASE_URL",
            "postgresql://postgres:postgres@localhost:5432/northwind",
        )
    )
    database_connect_timeout_seconds: int = field(
        default_factory=lambda: _env_int("DATABASE_CONNECT_TIMEOUT_SECONDS", "2")
    )
    statement_timeout_ms: int = field(
        default_factory=lambda: _env_int("STATEMENT_TIMEOUT_MS", "10000")
    )
    groq_api_key: str | None = field(
        default_factory=lambda: _env("GROQ_API_KEY") or None
    )
    groq_model: str = field(
        default_factory=lambda: _env("GROQ_MODEL", "llama-3.3-70b-versatile")
    )
    groq_request_timeout_seconds: int = field(
        default_factory=lambda: _env_int("GROQ_REQUEST_TIMEOUT_SECONDS", "30")
    )
    langsmith_tracing: bool = field(
        default_factory=lambda: _env("LANGSMITH_TRACING", "false").lower() == "true"
    )
    langsmith_api_key: str | None = field(
        default_factory=lambda: _env("LANGSMITH_API_KEY") or None
    )
    langsmith_project: str = field(
        default_factory=lambda: _env("LANGSMITH_PROJECT", "InsightSQL-AgentOps")
    )


def get_settings() -> Settings:
    return Settings()
