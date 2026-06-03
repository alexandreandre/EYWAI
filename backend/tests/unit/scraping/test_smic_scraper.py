"""Tests unitaires SMIC (primary + Sonar)."""

from datetime import date
from pathlib import Path

from bs4 import BeautifulSoup

from scraping.SMIC.SMIC import (
    applicable_segment_table_text,
    extract_smic_data,
)
from scraping.SMIC.SMIC_AI import _reference_core, extract_smic
from scraping.SMIC.spec import _equal, _extract_sig

FIXTURES = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "scraping"
    / "smic"
    / "urssaf_multi_revision.html"
)


def test_extract_june_2026_rates():
    soup = BeautifulSoup(FIXTURES.read_text(encoding="utf-8"), "html.parser")
    data = extract_smic_data(soup, reference_date=date(2026, 6, 2))
    assert data["cas_general"] == 12.31
    assert data["jeune_17_ans"] == 11.08
    assert data["jeune_moins_17_ans"] == 9.85
    assert data["smic_mensuel_brut"] == 1867.02


def test_applicable_segment_table_text_mentions_youth_rates():
    soup = BeautifulSoup(FIXTURES.read_text(encoding="utf-8"), "html.parser")
    text = applicable_segment_table_text(soup, reference_date=date(2026, 6, 2))
    assert "12.31" in text or "12,31" in text
    assert "11.08" in text or "11,08" in text
    assert "9.85" in text or "9,85" in text


def test_extract_smic_consensus_mocked(monkeypatch):
    soup = BeautifulSoup(FIXTURES.read_text(encoding="utf-8"), "html.parser")
    reference = extract_smic_data(soup, reference_date=date(2026, 6, 2))
    ref_core = _reference_core(reference)

    monkeypatch.setattr("scraping.SMIC.SMIC_AI.smic_module.fetch_soup", lambda: soup)
    monkeypatch.setattr(
        "scraping.SMIC.SMIC_AI.smic_module.extract_smic_data",
        lambda _soup: reference,
    )
    monkeypatch.setattr(
        "scraping.SMIC.SMIC_AI.extract_structured_json",
        lambda **kw: {
            "cas_general": 12.31,
            "jeune_17_ans": 11.08,
            "jeune_moins_17_ans": 9.85,
            "smic_mensuel_brut": 1867.02,
        },
    )

    sections = extract_smic()
    assert sections is not None
    assert _equal(sections, ref_core)


def test_sonar_youth_confusion_would_fail_consensus():
    """Repro du bug : Sonar renvoie 9.85 / 8.62 au lieu de 11.08 / 9.85."""
    primary = {
        "cas_general": 12.31,
        "jeune_17_ans": 11.08,
        "jeune_moins_17_ans": 9.85,
        "smic_mensuel_brut": 1867.02,
        "smic_horaire_brut": 12.31,
    }
    sonar_wrong = {
        "cas_general": 12.31,
        "jeune_17_ans": 9.85,
        "jeune_moins_17_ans": 8.62,
        "smic_mensuel_brut": 1867.02,
        "smic_horaire_brut": 12.31,
    }
    assert not _equal(primary, sonar_wrong)


def test_payload_signatures_match_on_fixture():
    soup = BeautifulSoup(FIXTURES.read_text(encoding="utf-8"), "html.parser")
    data = extract_smic_data(soup, reference_date=date(2026, 6, 2))
    payload = {"sections": {k: v for k, v in data.items() if k != "source"}}
    sig = _extract_sig(payload)
    assert sig["cas_general"] == 12.31
    assert sig["jeune_17_ans"] == 11.08
