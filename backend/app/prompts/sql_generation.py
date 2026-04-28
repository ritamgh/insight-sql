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
- Treat the BUSINESS QUESTION as authoritative. If it includes a user clarification, that clarification overrides defaults, assumptions, and retrieved examples.
- If the user chooses product order count, rank products by COUNT(DISTINCT order_details.order_id) AS order_count, not revenue.
- If the user chooses product units sold, rank products by SUM(order_details.quantity) AS units_sold, not revenue.
- FOREIGN KEY RULE: child_table.fk_column = parent_table.pk_column (never reversed).
- JOIN RULE: Every multi-table query MUST use explicit JOIN ... ON. No implicit joins (comma-separated FROM).
- TIME RULES: Use EXTRACT(YEAR FROM col) and DATE_TRUNC('month', col) for grouping.
- NORTHWIND DATE RULE: Northwind data is historical. For "recent", "last N days/months/years", or similar rolling windows, compare against the dataset's latest order date, not CURRENT_DATE.
- DATASET-RELATIVE WINDOW EXAMPLE: orders.order_date >= (SELECT MAX(orders.order_date) FROM orders) - INTERVAL '1 year'.
- Do not use CURRENT_DATE for Northwind order recency unless the user explicitly asks relative to today's real calendar date.
- EXAMPLE CONFLICT: If a provided example conflicts with the current schema, ignore the example.
"""


def build_sql_generation_prompt(
    refined_query: str,
    schema_context: str,
    retrieved_examples: list[dict[str, Any]] | None = None,
    last_error: str | None = None,
    last_sql: str | None = None,
) -> str:
    examples = retrieved_examples or []
    examples_block = "\n".join(
        f"Q: {example.get('question', '')}\nSQL: {example.get('sql', example.get('text', ''))}"
        for example in examples[:2]
    ) or "No examples retrieved."
    retry_guidance = ""
    if last_error:
        retry_guidance = (
            f"\nPREVIOUS SQL:\n{last_sql or ''}\nERROR: {last_error}\nFix the SQL above."
        )
    return f"""SCHEMA:
{schema_context}

EXAMPLES:
{examples_block}

BUSINESS QUESTION:
{refined_query}
{retry_guidance}

Return only SQL."""


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
