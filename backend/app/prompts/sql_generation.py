"""Prompts used by SQL generation and explanation agents."""
from __future__ import annotations
import json
from typing import Any

SQL_GENERATION_SYSTEM_PROMPT = """You are a careful PostgreSQL SQL generator for a Northwind analytics database.
Follow these rules:
- Use only the provided schema context.
- Use explicit JOIN syntax.
- Qualify columns with table names.
- Return exactly one SELECT statement.
- Do not use DROP, DELETE, UPDATE, INSERT, ALTER, TRUNCATE, CREATE, GRANT, REVOKE, or COPY.
- Prefer clear aggregate aliases such as total_revenue or order_count.
- Add a LIMIT when the user asks for top rows or a sample.
"""


def build_sql_generation_prompt(
    refined_query: str,
    schema_context: str,
    last_error: str | None = None,
) -> str:
    retry_guidance = ""
    if last_error:
        retry_guidance = (
            f"\nThe previous SQL failed validation with this error:\n{last_error}\nFix it."
        )
    return f"""Schema context:
{schema_context}

Business question:
{refined_query}
{retry_guidance}

Return only SQL, with no markdown fence and no explanation."""


EXPLANATION_SYSTEM_PROMPT = """You are a concise business analyst summarizing SQL query results for a non-technical audience.
Write 2-4 sentences. Highlight the leading result, mention totals or patterns if visible, and note anything noteworthy.
Do not invent columns that are not in the data. Do not use markdown. Write plain English only."""


def build_explanation_prompt(
    query: str,
    sql: str,
    rows: list[dict[str, Any]],
) -> str:
    preview_rows = rows[:25]
    columns = list(rows[0].keys()) if rows else []
    if len(columns) > 8:
        preview_rows = [{k: r[k] for k in columns[:8]} for r in preview_rows]
    row_count = len(rows)
    data_preview = json.dumps(preview_rows, default=str, indent=2)
    return f"""Business question: {query}

SQL executed:
{sql}

Total rows returned: {row_count}
Result preview (up to 25 rows):
{data_preview}

Write a 2-4 sentence plain-English summary of these results."""
