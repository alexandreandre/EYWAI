"""Tests du gate de validation humaine (helpers core/pending.py)."""

from core.pending import build_ai_candidate, config_changed, extract_citation, requires_human_gate
from utils import is_ai_scraper_label


def test_config_changed_full_mode():
    current = {"config_data": {"cas_general": 11.88, "annee": 2026}}
    assert config_changed("full", None, {"cas_general": 11.88}) is True
    assert config_changed("full", current, {"cas_general": 11.88, "annee": 2026}) is False
    assert config_changed("full", current, {"cas_general": 12.00, "annee": 2026}) is True


def test_config_changed_cotisations_ignores_timestamps():
    current = {
        "config_data": {
            "cotisations": [
                {"id": "csg", "salarial": 0.029, "last_checked_at": "2026-01-01"}
            ]
        }
    }
    same = {"cotisations": [{"id": "csg", "salarial": 0.029}]}
    diff = {"cotisations": [{"id": "csg", "salarial": 0.030}]}
    assert config_changed("cotisations", current, same) is False
    assert config_changed("cotisations", current, diff) is True


def test_extract_citation_reads_meta_source():
    payload = {
        "meta": {
            "source": [
                {"url": "https://www.urssaf.fr/x", "label": "URSSAF", "date_doc": "01/01/2026"}
            ]
        }
    }
    cit = extract_citation(payload)
    assert cit["citation_url"] == "https://www.urssaf.fr/x"
    assert cit["citation_date"] == "01/01/2026"


def test_build_ai_candidate_picks_ai_source():
    labels = ["SMIC.py", "SMIC_AI.py"]
    sigs = [{"v": 11.88}, {"v": 11.90}]
    payloads = [
        {"meta": {"source": [{"url": "https://urssaf.fr", "date_doc": ""}]}},
        {"meta": {"source": [{"url": "https://www.urssaf.fr/smic", "date_doc": "01/06/2026"}]}},
    ]
    candidate = build_ai_candidate(labels, sigs, payloads, is_ai=is_ai_scraper_label)
    assert candidate is not None
    assert candidate["label"] == "SMIC_AI.py"
    assert candidate["value"] == {"v": 11.90}
    assert candidate["citation_url"] == "https://www.urssaf.fr/smic"
    assert candidate["citation_date"] == "01/06/2026"


def test_build_ai_candidate_none_without_ai():
    labels = ["SMIC.py", "Other.py"]
    sigs = [{"v": 11.88}, {"v": 11.88}]
    payloads = [{}, {}]
    assert build_ai_candidate(labels, sigs, payloads, is_ai=is_ai_scraper_label) is None


def test_requires_human_gate_critical_only():
    assert requires_human_gate("critical", changed=True, decision_case="A", ai_divergence=False) is True
    assert requires_human_gate("critical", changed=False, decision_case="B", ai_divergence=False) is True
    assert requires_human_gate("critical", changed=False, decision_case="C", ai_divergence=False) is True
    assert requires_human_gate("critical", changed=False, decision_case="A", ai_divergence=True) is True
    assert requires_human_gate("critical", changed=False, decision_case="A", ai_divergence=False) is False
    assert requires_human_gate("standard", changed=True, decision_case="B", ai_divergence=True) is False
