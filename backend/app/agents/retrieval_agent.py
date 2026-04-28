"""Retrieval agent — attaches relevant schema context to state."""
from __future__ import annotations
from functools import lru_cache
from pathlib import Path
from typing import Any

from backend.app.db.northwind_full_schema import foreign_key_lines
from backend.app.db.northwind_schema import select_schema_context
from backend.app.rag.chunks import build_column_chunks
from backend.app.rag.examples import EXAMPLE_PAIRS
from backend.app.rag.index import RAGIndexMissing, load_chroma_indexes
from backend.app.rag.retrieval import bm25_search, hybrid_merge, semantic_search
from backend.app.schemas.state import AgentState


def retrieval_agent(state: AgentState) -> AgentState:
    query = state.get("refined_query") or state.get("query", "")
    if not state.get("use_rag", True):
        state["schema"] = select_schema_context(query)
        state["retrieved_schema_chunks"] = []
        state["retrieved_examples"] = []
        return state

    try:
        schema_collection, example_collection = _collections()
        schema_semantic = semantic_search(schema_collection, query, k=5)
        example_semantic = semantic_search(example_collection, query, k=5)
    except RAGIndexMissing:
        state["schema"] = select_schema_context(query)
        state["retrieved_schema_chunks"] = []
        state["retrieved_examples"] = []
        state["retrieval_warning"] = "RAG index missing; used legacy schema retrieval."
        return state

    schema_hits = hybrid_merge(
        schema_semantic,
        bm25_search(build_column_chunks(), query, k=5),
        k=3,
    )
    example_docs = [
        {**pair, "text": f"Q: {pair['question']}\nSQL: {pair['sql']}"}
        for pair in EXAMPLE_PAIRS
    ]
    example_hits = hybrid_merge(
        bm25_search(example_docs, query, k=5),
        example_semantic,
        k=2,
    )
    state["retrieved_schema_chunks"] = schema_hits
    state["retrieved_examples"] = _hydrate_examples(example_hits)
    state["schema"] = _format_schema(schema_hits)
    return state


@lru_cache(maxsize=1)
def _collections() -> tuple[Any, Any]:
    return load_chroma_indexes(Path(".rag_index"))


def _format_schema(chunks: list[dict[str, Any]]) -> str:
    chunk_lines = "\n".join(f"- {hit.get('text', '')}" for hit in chunks)
    fk_lines = "\n".join(f"- {line}" for line in foreign_key_lines())
    return f"""RELEVANT COLUMNS:
{chunk_lines}

FOREIGN KEY RELATIONSHIPS:
{fk_lines}"""


def _hydrate_examples(hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id = {pair["id"]: pair for pair in EXAMPLE_PAIRS}
    hydrated = []
    for hit in hits:
        example = dict(by_id.get(str(hit.get("id")), {}))
        example.update(hit)
        hydrated.append(example)
    return hydrated
