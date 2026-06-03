"""Tests unitaires du scraper PAS (sans appel réseau)."""

import importlib.util
from pathlib import Path

from scraping.PAS.PAS import _zone_from_caption, norm, scrape_bofip
from scraping.PAS.PAS_AI import (
    NB_TRANCHES,
    _date_from_bofip_url,
    build_sections,
    normalize_tranches,
    tranches_match_reference,
)

_PAS_AI = Path(__file__).resolve().parents[3] / "scraping" / "PAS" / "PAS_AI.py"


def test_date_from_bofip_url():
    url = (
        "https://bofip.impots.gouv.fr/bofip/11255-PGP.html/"
        "identifiant%3DBOI-BAREME-000037-20260407"
    )
    assert _date_from_bofip_url(url) == "07/04/2026"


def test_zone_from_caption_metropole():
    cap = "Grille … domiciliés en métropole et hors de France à compter du 1er mai 2026"
    assert _zone_from_caption(cap) == "metropole"


def test_zone_from_caption_guyane_before_metropole_keywords():
    cap = "Grille … domiciliés en Guyane et à Mayotte à compter du 1er mai 2026"
    assert _zone_from_caption(cap) == "guyane_mayotte"


def test_norm_strips_accents():
    assert norm("Métropole") == "metropole"


def test_normalize_tranches_requires_20_and_null_last():
    raw = [{"plafond": 1000.0, "taux_pct": 0.5} for _ in range(NB_TRANCHES - 1)]
    raw.append({"plafond": None, "taux_pct": 4.3})
    out = normalize_tranches(raw)
    assert out is not None
    assert len(out) == NB_TRANCHES
    assert out[-1]["plafond"] is None
    assert out[-1]["taux"] == 0.043
    assert out[0]["taux"] == 0.005


def test_tranches_match_reference():
    ref = [{"plafond": 1635.0, "taux": 0.0}, {"plafond": None, "taux": 0.43}]
    assert tranches_match_reference(ref, ref) is True
    bad = [{"plafond": 1636.0, "taux": 0.0}, {"plafond": None, "taux": 0.43}]
    assert tranches_match_reference(bad, ref) is False


def _sample_zone_tranches(first_plafond: float) -> list[dict]:
    tranches = []
    for i in range(NB_TRANCHES - 1):
        tranches.append({"plafond": first_plafond + i * 100.0, "taux": round(i * 0.005, 3)})
    tranches.append({"plafond": None, "taux": 0.43})
    return tranches


def test_pas_ai_and_primary_parse_same_html():
    html = """
    <html><body>
    <table><caption>Grille domiciliés en métropole</caption>
    <tr><td>Inférieure à 1 635 €</td><td>0,0 %</td></tr>
    <tr><td>Supérieure ou égale à 1 635 € et inférieure à 1 698 €</td><td>0,5 %</td></tr>
    </table>
    <table><caption>Guadeloupe, Réunion, Martinique</caption>
    <tr><td>Inférieure à 1 875 €</td><td>0,0 %</td></tr>
    <tr><td>Supérieure ou égale à 2 786 € et inférieure à 2 881 €</td><td>4,1 %</td></tr>
    </table>
    <table><caption>Guyane et Mayotte</caption>
    <tr><td>Inférieure à 2 008 €</td><td>0,0 %</td></tr>
    <tr><td>Supérieure ou égale à 2 930 € et inférieure à 3 026 €</td><td>4,1 %</td></tr>
    </table>
    </body></html>
    """

    class FakeResp:
        text = html

        @staticmethod
        def raise_for_status() -> None:
            return None

    import scraping.PAS.PAS as pas_mod

    original_get = pas_mod.requests.get
    pas_mod.requests.get = lambda *a, **k: FakeResp()
    try:
        a = scrape_bofip("https://bofip.impots.gouv.fr/test")
        b = scrape_bofip("https://bofip.impots.gouv.fr/test")
    finally:
        pas_mod.requests.get = original_get

    assert a == b
    assert a["guadeloupe_reunion_martinique"][1]["plafond"] == 2881.0


def test_build_sections_mocked_sonar(monkeypatch):
    reference = {
        "metropole": _sample_zone_tranches(1635.0),
        "guadeloupe_reunion_martinique": _sample_zone_tranches(1875.0),
        "guyane_mayotte": _sample_zone_tranches(2008.0),
    }

    import scraping.PAS.PAS_AI as pas_ai_mod

    monkeypatch.setattr(
        pas_ai_mod.pas_module,
        "fetch_bofip_soup",
        lambda url: object(),
    )
    monkeypatch.setattr(
        pas_ai_mod.pas_module,
        "_parse_zones_from_soup",
        lambda soup: reference,
    )
    monkeypatch.setattr(
        pas_ai_mod.pas_module,
        "zone_table_text",
        lambda soup, zone_key: f"tableau {zone_key}",
    )

    def fake_extract(**kwargs):
        zone = kwargs.get("schema_name", "").replace("pas_", "")
        ref = reference[zone]
        tranches = [
            {
                "plafond": t["plafond"],
                "taux_pct": round(t["taux"] * 100, 2),
            }
            for t in ref
        ]
        return {"tranches": tranches}

    monkeypatch.setattr(
        "scraping.PAS.PAS_AI.extract_structured_json",
        fake_extract,
    )
    sections = build_sections("https://bofip.impots.gouv.fr/bofip/BOI-BAREME-000037-20260407")
    assert sections is not None
    assert set(sections) == {
        "metropole",
        "guadeloupe_reunion_martinique",
        "guyane_mayotte",
    }
    assert len(sections["metropole"]) == NB_TRANCHES
    assert sections["guadeloupe_reunion_martinique"][0]["plafond"] == 1875.0
