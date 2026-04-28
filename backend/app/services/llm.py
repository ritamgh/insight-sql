"""Groq-backed LLM service for disambiguation, SQL generation, and explanation."""
from __future__ import annotations
import json
import re
from typing import Any

from backend.app.core.config import get_settings
from backend.app.prompts.disambiguation import (
    DISAMBIGUATION_SYSTEM_PROMPT,
    build_disambiguation_prompt,
)
from backend.app.prompts.sql_generation import (
    EXPLANATION_SYSTEM_PROMPT,
    SQL_GENERATION_SYSTEM_PROMPT,
    build_explanation_prompt,
    build_sql_generation_prompt,
)


class LLMUnavailableError(Exception):
    """Raised when Groq is not configured or cannot be reached."""


def generate_sql_with_groq(
    refined_query: str,
    schema_context: str,
    retrieved_examples: list[dict[str, Any]] | None = None,
    last_error: str | None = None,
    last_sql: str | None = None,
) -> str:
    settings = get_settings()
    if not settings.groq_api_key:
        raise LLMUnavailableError(
            "GROQ_API_KEY is not set. Add it to your .env file to enable SQL generation."
        )
    prompt_text = build_sql_generation_prompt(
        refined_query,
        schema_context,
        retrieved_examples or [],
        last_error=last_error,
        last_sql=last_sql,
    )
    raw = _invoke_groq(SQL_GENERATION_SYSTEM_PROMPT, prompt_text, settings)
    return _extract_sql(raw)


def disambiguate_with_groq(query: str, schema_summary: str) -> dict[str, Any]:
    settings = get_settings()
    if not settings.groq_api_key:
        raise LLMUnavailableError(
            "GROQ_API_KEY is not set. Cannot run LLM-based disambiguation."
        )
    prompt_text = build_disambiguation_prompt(query, schema_summary)
    raw = _invoke_groq(DISAMBIGUATION_SYSTEM_PROMPT, prompt_text, settings)
    return _extract_json(raw)


def generate_explanation_with_groq(
    query: str,
    sql: str,
    rows: list[dict[str, Any]],
) -> str:
    settings = get_settings()
    if not settings.groq_api_key:
        raise LLMUnavailableError(
            "GROQ_API_KEY is not set. Cannot generate an explanation."
        )
    prompt_text = build_explanation_prompt(query, sql, rows)
    raw = _invoke_groq(EXPLANATION_SYSTEM_PROMPT, prompt_text, settings)
    return raw.strip()


def _invoke_groq(system_prompt: str, task_prompt: str, settings: Any) -> str:
    try:
        from langchain_core.prompts import ChatPromptTemplate
        from langchain_groq import ChatGroq
    except ModuleNotFoundError as exc:
        raise LLMUnavailableError(
            "Groq dependencies are not installed. Install project requirements to enable LLM calls."
        ) from exc

    model = ChatGroq(
        model=settings.groq_model,
        temperature=0,
        max_retries=2,
        timeout=settings.groq_request_timeout_seconds,
        api_key=settings.groq_api_key,
    )
    chain = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "{task_prompt}"),
    ]) | model
    response = chain.invoke({"task_prompt": task_prompt})
    content = response.content
    if isinstance(content, list):
        return "\n".join(
            item.get("text", "") for item in content if isinstance(item, dict)
        )
    return str(content)


def _extract_sql(text: str) -> str:
    match = re.search(r"```(?:sql)?\s*(.*?)```", text, flags=re.IGNORECASE | re.DOTALL)
    if match:
        return match.group(1).strip()
    return text.strip()


def _extract_json(text: str) -> dict[str, Any]:
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not match:
        return _default_disambiguation()
    try:
        payload = json.loads(match.group(0))
    except json.JSONDecodeError:
        return _default_disambiguation()
    required = {"is_ambiguous", "clarification_question", "default_assumption"}
    if not required.issubset(payload):
        return _default_disambiguation()
    return {
        "is_ambiguous": bool(payload["is_ambiguous"]),
        "clarification_question": str(payload["clarification_question"] or ""),
        "default_assumption": str(payload["default_assumption"] or ""),
    }


def _default_disambiguation() -> dict[str, Any]:
    return {
        "is_ambiguous": False,
        "clarification_question": "",
        "default_assumption": "",
    }
