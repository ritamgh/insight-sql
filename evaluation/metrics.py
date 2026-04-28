"""Evaluation metric helpers."""
from __future__ import annotations
from typing import Any

from evaluation.normalize import normalize_rows


def execution_accuracy(predicted_rows: list[dict[str, Any]], gold_rows: list[dict[str, Any]]) -> float:
    return 1.0 if normalize_rows(predicted_rows) == normalize_rows(gold_rows) else 0.0


def execution_success(state: dict[str, Any]) -> float:
    return 0.0 if state.get("error") else 1.0


def error_recovery(state: dict[str, Any]) -> float:
    return 1.0 if state.get("retry_count", 0) > 0 and not state.get("error") else 0.0


def latency_ms(start: float, end: float) -> float:
    return round((end - start) * 1000, 2)
