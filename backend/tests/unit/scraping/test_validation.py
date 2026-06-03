"""Tests unitaires validation scraping."""

from core.validation import (
    validate_dialogue_social,
    validate_pss_sections,
    validate_smic_sections,
)


def test_validate_smic_ok():
    r = validate_smic_sections(
        {
            "annee": 2026,
            "cas_general": 12.31,
            "smic_horaire_brut": 12.31,
            "smic_mensuel_brut": 1867.02,
            "jeune_17_ans": 11.08,
            "jeune_moins_17_ans": 9.85,
        }
    )
    assert r.ok


def test_validate_smic_rejects_mixed_territory():
    r = validate_smic_sections(
        {
            "annee": 2026,
            "cas_general": 11.88,
            "smic_horaire_brut": 11.88,
            "smic_mensuel_brut": 1449.93,
        }
    )
    assert not r.ok


def test_validate_smic_bad_year():
    r = validate_smic_sections(
        {"annee": 2020, "cas_general": 12.0, "smic_horaire_brut": 12.0}
    )
    assert not r.ok


def test_validate_dialogue_non_null():
    assert validate_dialogue_social({"patronal": 0.00016}).ok
    assert not validate_dialogue_social({"patronal": None}).ok


def test_validate_pss():
    assert validate_pss_sections(
        {"annee": 2026, "annuel": 48060, "mensuel": 4005}
    ).ok
