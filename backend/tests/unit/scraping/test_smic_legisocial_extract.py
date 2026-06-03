"""Extraction SMIC depuis texte libre (LegiSocial, articles)."""

from datetime import date

from core.urssaf_parser import pick_applicable_smic_horaire_from_text


def test_pick_june_rate_when_multiple_mentions():
    text = (
        "Le smic horaire est fixé à 12,02 euros brut dans le cas général. "
        "Au 1er juin 2026 le smic horaire brut est de 12,31 €."
    )
    val = pick_applicable_smic_horaire_from_text(text, reference_date=date(2026, 6, 1))
    assert val == 12.31


def test_pick_january_rate_before_june():
    text = (
        "Au 1er janvier 2026 le smic horaire brut est de 12,02 €. "
        "Au 1er juin 2026 le smic horaire brut est de 12,31 €."
    )
    val = pick_applicable_smic_horaire_from_text(text, reference_date=date(2026, 3, 1))
    assert val == 12.02
