"""Create CSV and bar-chart summaries from evaluation JSONL output."""
from __future__ import annotations
import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


def build_report(jsonl_path: Path) -> tuple[Path, Path]:
    rows = [json.loads(line) for line in jsonl_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    grouped: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for row in rows:
        for metric in ("exec_accuracy", "exec_success", "error_recovery", "latency_ms"):
            grouped[row["config"]][metric].append(float(row[metric]))

    summary_rows = []
    for config, metrics in grouped.items():
        summary_rows.append({
            "config": config,
            **{metric: sum(values) / len(values) for metric, values in metrics.items()},
        })

    csv_path = jsonl_path.with_name(f"{jsonl_path.stem}_summary.csv")
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["config", "exec_accuracy", "exec_success", "error_recovery", "latency_ms"])
        writer.writeheader()
        writer.writerows(summary_rows)

    png_path = jsonl_path.with_name(f"{jsonl_path.stem}_bars.png")
    _write_chart(summary_rows, png_path)
    return csv_path, png_path


def _write_chart(rows: list[dict[str, Any]], path: Path) -> None:
    import os
    import tempfile

    os.environ.setdefault("MPLCONFIGDIR", tempfile.mkdtemp(prefix="matplotlib-"))
    import matplotlib.pyplot as plt

    configs = [row["config"] for row in rows]
    metrics = ["exec_accuracy", "exec_success", "error_recovery"]
    x = range(len(configs))
    width = 0.25
    fig, ax = plt.subplots(figsize=(8, 4))
    for offset, metric in enumerate(metrics):
        ax.bar([value + (offset - 1) * width for value in x], [row[metric] for row in rows], width, label=metric)
    ax.set_xticks(list(x), configs)
    ax.set_ylim(0, 1)
    ax.legend()
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
