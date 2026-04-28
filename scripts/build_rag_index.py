"""Build persistent Chroma RAG indexes."""
from __future__ import annotations
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.app.rag.index import build_chroma_indexes


if __name__ == "__main__":
    build_chroma_indexes(Path(".rag_index"))
    print("Built RAG index at .rag_index")
