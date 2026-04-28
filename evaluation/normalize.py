"""Normalize SQL result rows for execution-accuracy comparison."""
from __future__ import annotations
from decimal import Decimal, ROUND_HALF_UP
from typing import Any


def normalize_rows(rows: list[dict[str, Any]]) -> frozenset[tuple[tuple[str, Any], ...]]:
    normalized = []
    for row in rows:
        normalized.append(tuple(sorted(
            (str(key).lower(), _normalize_value(value))
            for key, value in row.items()
        )))
    return frozenset(normalized)


def _normalize_value(value: Any) -> Any:
    if isinstance(value, float):
        return float(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
    if isinstance(value, str):
        return value.lower()
    return value
