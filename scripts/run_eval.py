"""Run InsightSQL evaluation configs."""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from evaluation.report import build_report
from evaluation.runner import run_evaluation


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", choices=["baseline", "rag", "full", "all"], default="all")
    args = parser.parse_args()
    configs = ["baseline", "rag", "full"] if args.config == "all" else [args.config]
    result_path = run_evaluation(configs)
    csv_path, png_path = build_report(result_path)
    print(result_path)
    print(csv_path)
    print(png_path)


if __name__ == "__main__":
    main()
