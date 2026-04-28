"""Tests for hybrid retrieval helpers."""
from __future__ import annotations

from backend.app.rag.retrieval import bm25_search, hybrid_merge


def test_hybrid_merge_prefers_semantic_and_dedups():
    semantic = [{"id": "a", "text": "A"}, {"id": "b", "text": "B"}]
    bm25 = [{"id": "a", "text": "A2"}, {"id": "c", "text": "C"}]
    assert hybrid_merge(semantic, bm25, k=3) == [
        {"id": "a", "text": "A"},
        {"id": "b", "text": "B"},
        {"id": "c", "text": "C"},
    ]


def test_bm25_search_honors_k():
    corpus = [
        {"id": "customers", "text": "customer revenue orders"},
        {"id": "products", "text": "product inventory stock"},
    ]
    hits = bm25_search(corpus, "customer revenue", k=1)
    assert len(hits) == 1
    assert hits[0]["id"] == "customers"
