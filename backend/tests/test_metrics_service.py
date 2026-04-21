"""Unit tests for metrics aggregation logic."""

from app.services.metrics import _percentile


def test_percentile_empty() -> None:
    assert _percentile([], 0.95) is None


def test_percentile_single() -> None:
    assert _percentile([100], 0.95) == 100


def test_percentile_interpolates() -> None:
    vs = list(range(1, 101))  # 1..100
    p95 = _percentile(vs, 0.95)
    assert p95 is not None
    # 95th percentile of 1..100 (zero-indexed linear) lies at k=94.05
    # value[94] = 95, value[95] = 96, frac=0.05 → 95.05
    assert 95.0 <= p95 <= 96.0
