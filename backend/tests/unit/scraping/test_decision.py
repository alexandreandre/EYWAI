"""Tests de la classification multi-sources (cas A / B / C)."""

from core.decision import classify_decision


def _eq(a, b):
    return abs(a["v"] - b["v"]) < 1e-9


def test_dual_consensus_scraper_and_sonar_agree():
    labels = ["AGIRC-ARRCO.py", "AGIRC-ARRCO_AI.py"]
    sigs = [{"v": 0.0315}, {"v": 0.0315}]
    res = classify_decision(
        labels,
        sigs,
        primary_label="AGIRC-ARRCO.py",
        signatures_equal=_eq,
        dual_source_consensus=True,
    )
    assert res.case == "A"
    assert res.ok
    assert res.sources_agreement is True
    assert res.ai_divergence is False


def test_dual_consensus_fails_on_divergence():
    labels = ["AGIRC-ARRCO.py", "AGIRC-ARRCO_AI.py"]
    sigs = [{"v": 0.0315}, {"v": 0.0320}]
    res = classify_decision(
        labels,
        sigs,
        primary_label="AGIRC-ARRCO.py",
        signatures_equal=_eq,
        dual_source_consensus=True,
    )
    assert res.case == "C"
    assert not res.ok
    assert res.ai_divergence is True


def test_dual_consensus_primary_and_sonar_ignore_legisocial():
    """LegiSocial présent mais non compté — seul primary + Sonar."""
    labels = ["CSG.py", "CSG_LegiSocial.py", "CSG_AI.py"]
    sigs = [{"v": 0.029}, {"v": 0.029}, {"v": 0.029}]
    res = classify_decision(
        labels,
        sigs,
        primary_label="CSG.py",
        signatures_equal=_eq,
        dual_source_consensus=True,
    )
    assert res.ok
    assert res.sources_agreement is True


def test_dual_consensus_fails_without_sonar():
    labels = ["AGIRC-ARRCO.py"]
    sigs = [{"v": 0.0315}]
    res = classify_decision(
        labels,
        sigs,
        primary_label="AGIRC-ARRCO.py",
        signatures_equal=_eq,
        dual_source_consensus=True,
    )
    assert not res.ok
    assert "Sonar" in res.reason


def test_case_a_two_deterministic_agree():
    labels = ["Primary.py", "Secondary.py", "Witness_AI.py"]
    sigs = [{"v": 11.88}, {"v": 11.88}, {"v": 11.88}]
    res = classify_decision(
        labels, sigs, primary_label="Primary.py", signatures_equal=_eq
    )
    assert res.case == "A"
    assert res.ok
    assert res.sources_agreement is True
    assert res.ai_divergence is False
    assert res.deterministic_count == 2


def test_case_a_ai_diverges_is_tripwire():
    labels = ["Primary.py", "Secondary.py", "Witness_AI.py"]
    sigs = [{"v": 11.88}, {"v": 11.88}, {"v": 12.00}]
    res = classify_decision(
        labels, sigs, primary_label="Primary.py", signatures_equal=_eq
    )
    assert res.case == "A"
    assert res.ok
    assert res.sources_agreement is True
    assert res.ai_divergence is True


def test_case_b_smic_primary_and_ai_agree_legacy_mode():
    """Sans dual_source_consensus : ancien cas B (1 déterministe + IA)."""
    labels = ["SMIC.py", "SMIC_AI.py"]
    sigs = [{"v": 12.31}, {"v": 12.31}]
    res = classify_decision(
        labels,
        sigs,
        primary_label="SMIC.py",
        signatures_equal=_eq,
        dual_source_consensus=False,
    )
    assert res.case == "B"
    assert res.ok
    assert res.sources_agreement is False


def test_case_c_deterministic_disagree_primary_fallback():
    labels = ["SMIC.py", "Other.py"]
    sigs = [{"v": 11.88}, {"v": 99.0}]
    res = classify_decision(
        labels, sigs, primary_label="SMIC.py", signatures_equal=_eq
    )
    assert res.case == "C"
    assert res.ok
    assert res.ref_idx == 0
    assert res.sources_agreement is False


def test_discrepancies_flag_ai():
    labels = ["SMIC.py", "SMIC_AI.py"]
    sigs = [{"v": 11.88}, {"v": 11.88}]
    res = classify_decision(
        labels,
        sigs,
        primary_label="SMIC.py",
        signatures_equal=_eq,
        dual_source_consensus=True,
    )
    by_label = {d["label"]: d for d in res.discrepancies}
    assert by_label["SMIC.py"]["is_ai"] is False
    assert by_label["SMIC_AI.py"]["is_ai"] is True
