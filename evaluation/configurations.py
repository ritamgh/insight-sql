"""Pipeline configuration runners for ablation evaluation."""
from __future__ import annotations
from typing import Any

from backend.app.controller import run_agent_pipeline


def run_baseline(question: str) -> dict[str, Any]:
    return run_agent_pipeline(question, use_rag=False, use_validation_layers=False)


def run_rag(question: str) -> dict[str, Any]:
    return run_agent_pipeline(question, use_rag=True, use_validation_layers=False)


def run_full(question: str) -> dict[str, Any]:
    return run_agent_pipeline(question, use_rag=True, use_validation_layers=True)


CONFIG_RUNNERS = {
    "baseline": run_baseline,
    "rag": run_rag,
    "full": run_full,
}
