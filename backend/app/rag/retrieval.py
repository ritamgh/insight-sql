"""Hybrid semantic/BM25 retrieval utilities."""
from __future__ import annotations
import math
import re
from typing import Any


def semantic_search(collection: Any, query: str, k: int) -> list[dict[str, Any]]:
    result = collection.query(query_texts=[query], n_results=k)
    ids = result.get("ids", [[]])[0]
    documents = result.get("documents", [[]])[0]
    metadatas = result.get("metadatas", [[]])[0]
    distances = result.get("distances", [[]])[0] if result.get("distances") else [0.0] * len(ids)
    hits = []
    for idx, doc_id in enumerate(ids):
        distance = distances[idx] if idx < len(distances) else 0.0
        metadata = dict(metadatas[idx] or {}) if idx < len(metadatas) else {}
        hits.append({
            "id": doc_id,
            "text": documents[idx] if idx < len(documents) else metadata.get("text", ""),
            "score": 1.0 / (1.0 + float(distance or 0.0)),
            **metadata,
        })
    return hits


def bm25_search(corpus_texts: list[dict[str, Any]] | list[str], query: str, k: int) -> list[dict[str, Any]]:
    docs = [_coerce_doc(item, idx) for idx, item in enumerate(corpus_texts)]
    tokenized = [_tokens(doc["text"]) for doc in docs]
    query_tokens = _tokens(query)
    if not docs or not query_tokens:
        return []
    try:
        from rank_bm25 import BM25Okapi

        model = BM25Okapi(tokenized)
        scores = model.get_scores(query_tokens)
    except Exception:
        scores = [_simple_bm25_score(tokens, query_tokens, tokenized) for tokens in tokenized]
    ranked = sorted(zip(docs, scores), key=lambda pair: pair[1], reverse=True)
    return [{**doc, "score": float(score)} for doc, score in ranked[:k]]


def hybrid_merge(semantic_hits: list[dict[str, Any]], bm25_hits: list[dict[str, Any]], k: int) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    for hit in [*semantic_hits, *bm25_hits]:
        hit_id = str(hit.get("id") or hit.get("text"))
        if hit_id in seen:
            continue
        seen.add(hit_id)
        merged.append(hit)
        if len(merged) >= k:
            break
    return merged


def _coerce_doc(item: dict[str, Any] | str, idx: int) -> dict[str, Any]:
    if isinstance(item, dict):
        text = str(item.get("text") or item.get("question") or "")
        return {"id": str(item.get("id", idx)), "text": text, **item}
    return {"id": str(idx), "text": item}


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9_]+", text.lower())


def _simple_bm25_score(doc_tokens: list[str], query_tokens: list[str], corpus: list[list[str]]) -> float:
    score = 0.0
    doc_len = len(doc_tokens) or 1
    avg_len = sum(len(doc) for doc in corpus) / max(len(corpus), 1)
    for term in query_tokens:
        freq = doc_tokens.count(term)
        if not freq:
            continue
        docs_with_term = sum(1 for doc in corpus if term in doc)
        idf = math.log((len(corpus) - docs_with_term + 0.5) / (docs_with_term + 0.5) + 1)
        score += idf * (freq * 2.5) / (freq + 1.5 * (1 - 0.75 + 0.75 * doc_len / max(avg_len, 1)))
    return score
