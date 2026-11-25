"""Retrieval helpers for the CV tailor agent.

A small local retriever: it splits the knowledge file into paragraphs and returns
the ones that share the most words with the query. No external index is needed.
"""

import re
from pathlib import Path

KNOWLEDGE_FILE = Path(__file__).parent / "knowledge" / "cv_guidelines.txt"
_WORD = re.compile(r"\w+")


def _chunks(text: str) -> list[str]:
    return [chunk.strip() for chunk in text.split("\n\n") if chunk.strip()]


def _words(text: str) -> set[str]:
    return {word.lower() for word in _WORD.findall(text) if len(word) > 2}


def retrieve(query: str, k: int = 3, path: Path = KNOWLEDGE_FILE) -> list[str]:
    """Return up to k paragraphs from the knowledge file that best match the query."""
    if not path.is_file():
        return []
    chunks = _chunks(path.read_text(encoding="utf-8"))
    query_words = _words(query)
    scored = sorted(
        ((len(query_words & _words(chunk)), index, chunk) for index, chunk in enumerate(chunks)),
        key=lambda item: (-item[0], item[1]),
    )
    return [chunk for score, _, chunk in scored[:k] if score > 0]