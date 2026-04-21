"""Unit tests for hybrid search helpers (pure logic; no DB)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.schemas.search import SearchHit
from app.services.search import _snippet, merge_hits


def test_snippet_centers_on_match() -> None:
    text = "A" * 100 + "needle" + "B" * 100
    snip = _snippet(text, "needle", length=60)
    assert "needle" in snip


def test_snippet_missing_term_returns_prefix() -> None:
    assert _snippet("hello world", "missing", length=5) == "hello"


def _hit(kind: str, id_: uuid.UUID, score: float, matched_by: str) -> SearchHit:
    return SearchHit(
        kind=kind,  # type: ignore[arg-type]
        id=id_,
        score=score,
        snippet="x",
        matched_by=matched_by,  # type: ignore[arg-type]
        signal_type="experiment" if kind == "signal" else None,
        title="t" if kind == "paper" else None,
        created_at=datetime.now(UTC),
    )


def test_merge_hits_dedupes_and_marks_both() -> None:
    pid = uuid.uuid4()
    kw = [_hit("paper", pid, 1.0, "keyword")]
    emb = [_hit("paper", pid, 0.85, "embedding")]
    merged = merge_hits(kw, emb)
    assert len(merged) == 1
    assert merged[0].matched_by == "both"
    assert merged[0].score == 1.0


def test_merge_hits_sorts_by_score() -> None:
    a = _hit("signal", uuid.uuid4(), 0.4, "keyword")
    b = _hit("paper", uuid.uuid4(), 0.9, "embedding")
    c = _hit("paper", uuid.uuid4(), 0.2, "keyword")
    merged = merge_hits([a], [b], [c])
    assert [h.score for h in merged] == [0.9, 0.4, 0.2]
