"""Tests du parseur URSSAF générique (segments, dates, territoires)."""

from datetime import date

from bs4 import BeautifulSoup

from core.urssaf_parser import (
    iter_segments_from_soup,
    parse_french_amount,
    parse_french_effective_date,
    select_applicable_segment,
    smic_monthly_hours,
    territory_from_text,
)
from tests.unit.scraping.helpers import load_scraping_fixture


def test_parse_french_amount():
    assert parse_french_amount("1 823,03 €") == 1823.03
    assert parse_french_amount("12,31 €") == 12.31


def test_parse_effective_date_june():
    d = parse_french_effective_date("Au 1er juin 2026", default_year=2026)
    assert d == date(2026, 6, 1)


def test_territory_mayotte():
    assert territory_from_text("À Mayotte") == "overseas"
    assert territory_from_text("Métropole et DROM") == "mainland"


def test_select_june_revision_over_january():
    html = """
    <table>
    <tr><td>2026</td></tr>
    <tr><td>Au 1er janvier 2026</td></tr>
    <tr><td>Smic horaire brut</td><td>12,02 €</td></tr>
    <tr><td>mensuel</td><td>1 823,03 €</td></tr>
    <tr><td>Au 1er juin 2026</td></tr>
    <tr><td>Smic horaire brut</td><td>12,31 €</td></tr>
    <tr><td>mensuel</td><td>1 867,02 €</td></tr>
    </table>
    """
    segments = iter_segments_from_soup(BeautifulSoup(html, "html.parser"))
    seg = select_applicable_segment(
        segments, reference_date=date(2026, 6, 1), target_year=2026
    )
    assert seg is not None
    assert seg.label_values.get("smic horaire brut") == 12.31


def test_excludes_mayotte_block():
    html = load_scraping_fixture("smic", "urssaf_multi_revision.html")
    segments = iter_segments_from_soup(BeautifulSoup(html, "html.parser"))
    seg = select_applicable_segment(
        segments, reference_date=date(2026, 6, 15), target_year=2026
    )
    assert seg is not None
    assert seg.territory == "mainland"
    assert seg.label_values.get("smic horaire brut") == 12.31
    assert seg.label_values.get("mensuel") == 1867.02


def test_smic_monthly_hours():
    assert 151.0 < smic_monthly_hours() < 152.0
