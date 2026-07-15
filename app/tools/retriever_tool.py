"""Simple local retriever over sample docs (no external vector DB required)."""

from __future__ import annotations

import re
from pathlib import Path

from app.config import get_settings
from app.schemas.meeting_record import ContextSnippet


def _tokenize(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", text.lower()) if len(t) > 2}


def _score(query_tokens: set[str], doc_text: str) -> float:
    doc_tokens = _tokenize(doc_text)
    if not query_tokens or not doc_tokens:
        return 0.0
    overlap = query_tokens & doc_tokens
    return len(overlap) / len(query_tokens)


def load_sample_docs(docs_dir: Path | None = None) -> list[dict[str, str]]:
    settings = get_settings()
    root = docs_dir or (settings.data_dir / "sample_docs")
    docs: list[dict[str, str]] = []
    if not root.exists():
        return docs
    for path in sorted(root.glob("*.md")):
        docs.append(
            {
                "doc_id": path.stem,
                "title": path.stem.replace("_", " ").title(),
                "text": path.read_text(encoding="utf-8"),
            }
        )
    return docs


def retrieve_context(
    query: str,
    *,
    top_k: int = 3,
    docs_dir: Path | None = None,
) -> list[ContextSnippet]:
    docs = load_sample_docs(docs_dir)
    tokens = _tokenize(query)
    scored: list[ContextSnippet] = []
    for doc in docs:
        s = _score(tokens, doc["text"])
        if s > 0:
            # Take first non-empty paragraph as snippet.
            paras = [p.strip() for p in doc["text"].split("\n\n") if p.strip()]
            snippet = paras[1] if len(paras) > 1 else (paras[0] if paras else doc["text"][:300])
            scored.append(
                ContextSnippet(
                    doc_id=doc["doc_id"],
                    title=doc["title"],
                    text=snippet[:500],
                    score=round(s, 3),
                )
            )
    scored.sort(key=lambda c: c.score, reverse=True)
    return scored[:top_k]


def lookup_past_action_items(project: str | None = None) -> list[ContextSnippet]:
    """Mock 'lookup past action items' tool over sample docs."""
    query = f"action items open {project or ''} owner due"
    return retrieve_context(query, top_k=2)
