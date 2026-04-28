"""Run golden-set evaluations and emit JSONL results."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Iterable

from backend.app.db.connection import fetch_rows
from backend.app.db.demo_executor import fetch_demo_rows
from backend.app.db.health import is_database_connection_error
from evaluation.configurations import CONFIG_RUNNERS
from evaluation.golden_dataset import GOLDEN_QUESTIONS
from evaluation.metrics import error_recovery, execution_accuracy, execution_success, latency_ms


def run_evaluation(configs: Iterable[str]) -> Path:
    result_dir = Path("evaluation/results")
    result_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = result_dir / f"{ts}.jsonl"
    with path.open("w", encoding="utf-8") as handle:
        for question in GOLDEN_QUESTIONS:
            gold_rows = _fetch_gold_rows(str(question["gold_sql"]))
            for config in configs:
                runner = CONFIG_RUNNERS[config]
                started = perf_counter()
                state = runner(str(question["question"]))
                ended = perf_counter()
                record = {
                    "id": question["id"],
                    "config": config,
                    "question": question["question"],
                    "predicted_sql": state.get("sql", ""),
                    "gold_sql": question["gold_sql"],
                    "exec_accuracy": execution_accuracy(state.get("result", []), gold_rows),
                    "exec_success": execution_success(state),
                    "error_recovery": error_recovery(state),
                    "latency_ms": latency_ms(started, ended),
                    "validation_layers_triggered": state.get("validation_layers_triggered", []),
                    "failed_layer": state.get("failed_layer"),
                    "retry_count": state.get("retry_count", 0),
                }
                handle.write(json.dumps(record, default=str) + "\n")
    return path


def _fetch_gold_rows(sql: str) -> list[dict]:
    try:
        return fetch_rows(sql)
    except Exception as exc:
        if is_database_connection_error(exc):
            return fetch_demo_rows(sql)
        return []
