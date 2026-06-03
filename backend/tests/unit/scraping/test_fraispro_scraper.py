"""Tests unitaires frais pro (sans réseau)."""

from scraping.fraispro._logic import core_signature, equal_core
from scraping.fraispro.fraispro import scrape_all_sections, section_text
from scraping.fraispro.fraispro_AI import build_sections

HTML = """
<html><body>
<h2 id="ancre-repas">Repas</h2>
<table class="d-none d-md-table"><tbody>
<tr><th>Repas sur le lieu de travail</th><td>7,50 €</td></tr>
<tr><th>Repas non contraint d'utiliser</th><td>10,40 €</td></tr>
<tr><th>Repas au restaurant</th><td>21,40 €</td></tr>
</tbody></table>
<h2 id="ancre-petit-deplacement">Petit déplacement</h2>
<table class="d-none d-md-table"><tbody>
<tr><th>De 5 à 10 km</th><td>3,00 €</td></tr>
</tbody></table>
<h2 id="ancre-grand-deplacement">Grand déplacement</h2>
<h3>Déplacements en métropole</h3>
<table class="d-none d-md-table"><tbody>
<tr><th>3 mois</th><td>21,40 €</td><td>76,60 €</td><td>56,80 €</td></tr>
</tbody></table>
<h2 id="ancre-mutation-professionnelle">Mutation</h2>
<div class="tabs_custom_2"><div role="tablist">
<button aria-controls="p1">Hébergement provisoire</button>
<button aria-controls="p2">Hébergement définitif</button>
</div>
<div id="p1"><table class="d-none d-md-table"><tbody>
<tr class="table_custom__tbody"><td>x</td><td>85,10 €</td></tr>
</tbody></table></div>
<div id="p2"><table class="d-none d-md-table"><tbody>
<tr><td>installation dans le nouveau logement</td><td>1 705,70 €</td></tr>
<tr><td>Majoration par enfant</td><td>142,20 €</td></tr>
<tr><td>maximum</td><td>2 132,10 €</td></tr>
</tbody></table></div></div>
<h2 id="ancre-forfait-mobilites-durables">Mobilité</h2>
<div class="tabs_custom_2"><div role="tablist">
<button aria-controls="m1">Employeurs privés</button>
<button aria-controls="m2">Employeurs publics</button>
</div>
<div id="m1"><table class="d-none d-md-table"><tbody>
<tr><td>FMD</td><td>600,00 €</td></tr>
<tr><td>transports publics</td><td>900,00 €</td></tr>
<tr><td>carburant</td><td>600,00 € et 300,00 €</td></tr>
</tbody></table></div>
<div id="m2"><table class="d-none d-md-table"><tbody>
<tr><td>Entre 30 et 59 jours</td><td>100,00 €</td></tr>
</tbody></table></div></div>
<h2 id="ancre-teletravail-utilisation-de-mater">Télétravail</h2>
<h3>Indemnité forfaitaire de télétravail</h3>
<div class="tabs_custom_2"><div role="tablist">
<button aria-controls="t1">non prévue</button>
<button aria-controls="t2">prévue par une convention</button>
</div>
<div id="t1"><table class="d-none d-md-table"><tbody>
<tr><td>Par jour de télétravail</td><td>2,70 € et 59,40 €</td></tr>
<tr><td>Par mois</td><td>11,00 €</td></tr>
</tbody></table></div>
<div id="t2"><table class="d-none d-md-table"><tbody>
<tr><td>Par jour de télétravail</td><td>3,30 € et 72,60 €</td></tr>
<tr><td>Par mois</td><td>13,20 €</td></tr>
</tbody></table></div></div>
<h3>Indemnité forfaitaire liée à l'utilisation de matériels informatiques et de logiciels</h3>
<table class="d-none d-md-table"><tbody>
<tr class="table_custom__tbody"><td>x</td><td>55,20 €</td></tr>
</tbody></table>
</body></html>
"""


def _fake_soup():
    from bs4 import BeautifulSoup

    return BeautifulSoup(HTML, "html.parser")


def test_section_text_includes_tables():
    soup = _fake_soup()
    text = section_text(soup, "ancre-repas")
    assert "7,50" in text
    assert "sur le lieu de travail" in text.lower()


def test_scrape_all_sections_minimal_html():
    soup = _fake_soup()
    data = scrape_all_sections(soup)
    assert data["repas"]["sur_lieu_travail"] == 7.5
    assert len(data["petit_deplacement"]) == 1
    assert data["grand_deplacement"]["metropole"][0]["repas"] == 21.4


def test_build_sections_mocked_sonar(monkeypatch):
    import scraping.fraispro.fraispro_AI as ai_mod

    reference = scrape_all_sections(_fake_soup())

    monkeypatch.setattr(ai_mod.fraispro_module, "fetch_soup", lambda url: _fake_soup())
    monkeypatch.setattr(
        ai_mod.fraispro_module,
        "scrape_all_sections",
        lambda soup: reference,
    )

    def fake_extract(**kwargs):
        name = kwargs.get("schema_name", "")
        if name == "fraispro_repas":
            return reference["repas"]
        if name == "fraispro_petit_deplacement":
            return {"petit_deplacement": reference["petit_deplacement"]}
        if name == "fraispro_grand_deplacement_metropole":
            return {"metropole": reference["grand_deplacement"]["metropole"]}
        if name == "fraispro_grand_deplacement_om1":
            return {
                "outre_mer_groupe1": reference["grand_deplacement"]["outre_mer_groupe1"]
            }
        if name == "fraispro_grand_deplacement_om2":
            return {
                "outre_mer_groupe2": reference["grand_deplacement"]["outre_mer_groupe2"]
            }
        if name == "fraispro_mutation_professionnelle":
            return reference["mutation_professionnelle"]
        if name == "fraispro_mobilite_durable":
            return reference["mobilite_durable"]
        if name == "fraispro_teletravail":
            return reference["teletravail"]
        return None

    monkeypatch.setattr(
        "scraping.fraispro.fraispro_AI.extract_structured_json",
        fake_extract,
    )
    monkeypatch.setattr(
        ai_mod,
        "extract_grand_deplacement",
        lambda soup, ref, cd: reference["grand_deplacement"],
    )
    sections = build_sections()
    assert sections is not None
    sig_a = core_signature({"id": "frais_pro", "libelle": "a", "sections": reference})
    sig_b = core_signature({"id": "frais_pro", "libelle": "b", "sections": sections})
    assert equal_core(sig_a, sig_b)
