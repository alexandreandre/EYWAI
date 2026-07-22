# backend/tests/scraping/test_ai_scalar_spec.py
import sys
from pathlib import Path

SCRAPING = Path(__file__).resolve().parents[2] / "scraping"
if str(SCRAPING) not in sys.path:
    sys.path.insert(0, str(SCRAPING))

from core.ai_scalar_spec import build_ai_scalar_spec  # noqa: E402


def _spec():
    return build_ai_scalar_spec(
        scraper_name="DEMO",
        config_key="demo",
        ai_script_path="/tmp/demo_AI.py",
        keys=["a", "b"],
        bounds={"a": (0.0, 1.0), "b": (0.0, 1.0)},
        setters={"a": ["a"], "b": ["nested", "b"]},
        comment="demo",
    )


def test_signature_reads_valeurs():
    spec = _spec()
    sig = spec.extract_signature({"valeurs": {"a": 0.1, "b": 0.2}})
    assert sig == {"a": 0.1, "b": 0.2}


def test_equal_true_and_false():
    spec = _spec()
    assert spec.signatures_equal({"a": 0.1, "b": 0.2}, {"a": 0.1, "b": 0.2})
    assert not spec.signatures_equal({"a": 0.1, "b": 0.2}, {"a": 0.9, "b": 0.2})


def test_validate_rejects_out_of_range():
    spec = _spec()
    assert spec.validate_signature({"a": 0.5, "b": 0.5}).ok
    assert not spec.validate_signature({"a": 5.0, "b": 0.5}).ok


def test_merge_preserves_existing_and_sets_nested():
    spec = _spec()
    current = {"config_data": {"a": 0.0, "nested": {"b": 0.0, "keep": True}, "other": 1}}
    out = spec.build_config_data({"a": 0.1, "b": 0.2}, current)
    assert out["a"] == 0.1
    assert out["nested"]["b"] == 0.2
    assert out["nested"]["keep"] is True   # jamais reconstruit
    assert out["other"] == 1               # clés voisines préservées


def test_merge_requires_current_when_flagged():
    spec = _spec()
    import pytest
    with pytest.raises(ValueError):
        spec.build_config_data({"a": 0.1, "b": 0.2}, None)


def test_spec_is_human_gated_mono_source():
    spec = _spec()
    assert spec.tier == "critical"
    assert spec.dual_source_consensus is False
    assert spec.source_key == "DEMO"
