"""Tests for result normalization."""
from __future__ import annotations

from evaluation.normalize import normalize_rows


def test_normalize_rows_rounds_and_ignores_order():
    left = [{"Name": "ALFKI", "Revenue": 10.125}, {"Name": "BLAUS", "Revenue": 2.0}]
    right = [{"revenue": 2.0, "name": "blaus"}, {"revenue": 10.13, "name": "alfki"}]
    assert normalize_rows(left) == normalize_rows(right)
