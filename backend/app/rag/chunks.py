"""Build text chunks from Northwind schema metadata."""
from __future__ import annotations
from typing import Any

from backend.app.db.northwind_full_schema import FOREIGN_KEYS, TABLE_COLUMNS


def build_column_chunks() -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    for table, columns in TABLE_COLUMNS.items():
        for column, description in columns.items():
            fks = _foreign_keys_for(table, column)
            text = (
                f"Table: {table}. Column: {column}. Type: {description}. "
                f"FKs: {', '.join(fks) if fks else 'none'}"
            )
            chunks.append({
                "id": f"{table}.{column}",
                "table": table,
                "column": column,
                "text": text,
            })
    return chunks


def _foreign_keys_for(table: str, column: str) -> list[str]:
    lines: list[str] = []
    for child, child_col, parent, parent_col in FOREIGN_KEYS:
        if child == table and child_col == column:
            lines.append(f"{child}.{child_col} -> {parent}.{parent_col}")
        if parent == table and parent_col == column:
            lines.append(f"{child}.{child_col} -> {parent}.{parent_col}")
    return lines
