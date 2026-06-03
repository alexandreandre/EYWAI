"""Tests consensus scraping."""

from core.consensus import consensus_satisfied, prefer_primary_on_divergence


def test_consensus_two_equal():
    sigs = [{"a": 1.0}, {"a": 1.0}]
    ok, idx = consensus_satisfied(sigs, lambda x, y: x["a"] == y["a"])
    assert ok
    assert idx == 0


def test_consensus_divergence():
    sigs = [{"a": 1.0}, {"a": 2.0}]
    ok, _idx = consensus_satisfied(sigs, lambda x, y: x["a"] == y["a"])
    assert not ok


def test_prefer_primary_on_divergence():
    labels = ["primary.py", "secondary.py"]
    sigs = [{"v": 1.0}, {"v": 2.0}]
    ok, ref = prefer_primary_on_divergence(
        False,
        0,
        labels,
        sigs,
        "primary.py",
        lambda s: bool(s),
    )
    assert ok
    assert ref == 0
    assert sigs[ref]["v"] == 1.0
