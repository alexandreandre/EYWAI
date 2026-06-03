"""Tests unitaires avantages en nature (sans réseau)."""

from scraping.Avantages._logic import cores_equal, logement_values_equal, payload_to_core
from scraping.Avantages.Avantages import make_payload, scrape_from_soup, section_table_text
from scraping.Avantages.Avantages_AI import build_payload

HTML = """
<html><body>
<h3 id="ancre-repas">Repas</h3>
<table><tr><th>Valeur forfaitaire 1 repas</th><td>5,50 €</td></tr></table>
<h3 id="ancre-titre-restaurant">Titres-restaurant</h3>
<table><tr><th>Exonération maximale</th><td>7,32 €</td></tr></table>
<h3 id="ancre-logement">Logement</h3>
<table><tbody>
<tr><th>Inférieure ou égale à 2 002,50 €</th><td>79,70 €</td><td>42,60 €</td></tr>
<tr><th>Inférieure ou égale à 2 402,99 €</th><td>93,00 €</td><td>59,70 €</td></tr>
<tr><th>Au-delà de 6 007,50 €</th><td>225,60 €</td><td>212,30 €</td></tr>
</tbody></table>
</body></html>
"""


def _fake_soup():
    from bs4 import BeautifulSoup

    return BeautifulSoup(HTML, "lxml")


def test_section_table_text_repas():
    assert "5,50" in section_table_text(_fake_soup(), "repas")


def test_logement_values_equal_ignores_tranche():
    ref = [
        {"remuneration_max_eur": 2002.5, "valeur_1_piece_eur": 79.7, "valeur_par_piece_suppl_eur": 42.6},
    ]
    got = [
        {"remuneration_max_eur": 2002.49, "valeur_1_piece_eur": 79.7, "valeur_par_piece_suppl_eur": 42.6},
    ]
    assert logement_values_equal(got, ref) is True


def test_build_payload_mocked_sonar(monkeypatch):
    import scraping.Avantages.Avantages_AI as ai_mod

    reference = scrape_from_soup(_fake_soup())
    ref_core = payload_to_core(reference)

    monkeypatch.setattr(ai_mod.av_module, "fetch_soup", lambda: _fake_soup())
    monkeypatch.setattr(
        ai_mod.av_module, "scrape_from_soup", lambda soup: reference
    )

    def fake_extract(**kwargs):
        name = kwargs.get("schema_name", "")
        if name == "avantages_repas":
            return {"repas": ref_core["repas"]}
        if name == "avantages_titre":
            return {"titre_restaurant": ref_core["titre"]}
        if name == "avantages_logement":
            return {
                "logement": [
                    {
                        "remuneration_max": row["remuneration_max_eur"],
                        "valeur_1_piece": row["valeur_1_piece_eur"],
                        "valeur_par_piece": row["valeur_par_piece_suppl_eur"],
                    }
                    for row in ref_core["logement"]
                ]
            }
        return None

    monkeypatch.setattr(
        "scraping.Avantages.Avantages_AI.extract_structured_json",
        fake_extract,
    )
    payload = build_payload()
    assert payload is not None
    assert cores_equal(payload_to_core(reference), payload_to_core(payload))
