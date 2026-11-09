"""Bulletin de janvier 2027 : le modèle de l'article 1er de l'arrêté (R-273).

Arrêté du 25/02/2016 modifié par l'arrêté du 31/01/2023 (JORF du 07/02/2023,
texte 18) ; modèle adapté permis jusqu'au 01/01/2027 (arrêté du 11/08/2025).
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest
from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.modules.payroll.documents.bulletin_view import construire_vue_bulletin, modele_definitif
from tests.unit.payroll.test_bulletin_view import bulletin_minimal

pytestmark = pytest.mark.unit

TEMPLATES = Path(__file__).resolve().parents[3] / "app" / "runtime" / "payroll" / "templates"


def _ligne(coti_id, libelle, salarial, patronal):
    return {
        "coti_id": coti_id,
        "libelle": libelle,
        "base": 2000.0,
        "taux_salarial": 0.01,
        "montant_salarial": salarial,
        "montant_patronal": patronal,
    }


def _bulletin(annee=2027, mois=1) -> dict:
    b = copy.deepcopy(bulletin_minimal())
    b["en_tete"].update(annee=annee, mois=mois)
    b["salaire_brut"] = 2000.0
    b["net_a_payer"] = 1500.0
    b["synthese_net"] = {
        "net_imposable": 1600.0,
        "montant_net_social": 1550.0,
        "net_social_avant_impot": 1550.0,
    }
    b["primes_non_soumises"] = [{"libelle": "Frais de transports", "montant": 50.0}]
    b["cotisations_officielles"] = [
        {
            "code": "sante",
            "libelle": "Santé",
            "lignes": [_ligne("mutuelle", "Mutuelle", 20.0, 30.0)],
            "total_salarial": 20.0,
            "total_patronal": 30.0,
        },
        {
            "code": "retraite",
            "libelle": "Retraite",
            "lignes": [
                _ligne("vieillesse", "Sécurité sociale plafonnée", 100.0, 160.0),
                _ligne("retraite_sup", "Retraite supplémentaire", 10.0, 15.0),
            ],
            "total_salarial": 110.0,
            "total_patronal": 175.0,
        },
        {
            "code": "csg_non_deductible",
            "libelle": "CSG/CRDS non déductible",
            "lignes": [_ligne("csg_nd", "CSG/CRDS", 50.0, 0.0)],
            "total_salarial": 50.0,
            "total_patronal": 0.0,
        },
        {
            "code": "exonerations",
            "libelle": "Exonérations",
            "lignes": [_ligne("reduction_generale", "Réduction générale", 0.0, -200.0)],
            "total_salarial": 0.0,
            "total_patronal": -200.0,
        },
    ]
    return b


def _libelles(vue) -> list[str]:
    return [l["libelle"] for l in vue["lignes"]]


def test_le_modele_definitif_commence_en_janvier_2027():
    assert modele_definitif(_bulletin(2027, 1)) is True
    assert modele_definitif(_bulletin(2026, 12)) is False
    assert modele_definitif({}) is False


def test_decembre_2026_reste_au_modele_actuel():
    vue = construire_vue_bulletin(_bulletin(2026, 12))
    assert "TOTAL DES RETENUES" in _libelles(vue)
    assert "TOTAL DES COTISATIONS ET CONTRIBUTIONS OBLIGATOIRES" not in _libelles(vue)
    assert vue["pied"]["remboursements"] == [] and vue["pied"]["modele_definitif"] is False


def test_janvier_2027_libelles_et_ordre_de_l_arrete():
    vue = construire_vue_bulletin(_bulletin())
    libelles = _libelles(vue)
    assert libelles.index("COTISATIONS ET CONTRIBUTIONS SOCIALES OBLIGATOIRES") < libelles.index(
        "Santé"
    )
    assert "CSG/CRDS non déductible de l'impôt sur le revenu" in libelles
    total = libelles.index("TOTAL DES COTISATIONS ET CONTRIBUTIONS OBLIGATOIRES")
    assert libelles.index("EXONÉRATIONS ET ALLÈGEMENTS DE COTISATIONS") == total + 1
    assert libelles.index("COTISATIONS ET CONTRIBUTIONS SOCIALES FACULTATIVES") == total + 2
    assert "TOTAL DES RETENUES" not in libelles and "NET IMPOSABLE" not in libelles


def test_janvier_2027_le_total_obligatoire_laisse_les_facultatives():
    vue = construire_vue_bulletin(_bulletin())
    total = next(l for l in vue["lignes"] if l["libelle"].startswith("TOTAL DES COTISATIONS"))
    # 20 + 100 + 50 (la retraite supplémentaire est facultative ; la CSG y entre).
    assert total["montant_salarial"] == pytest.approx(170.0)
    assert total["montant_patronal"] == pytest.approx(190.0)


def test_janvier_2027_pied_sans_dont_evolution_et_remboursements():
    vue = construire_vue_bulletin(_bulletin())
    pied = vue["pied"]
    assert pied["evolution_remuneration"] is None and pied["modele_definitif"] is True
    assert [l["libelle"] for l in pied["remboursements"]] == ["Frais de transports"]


def test_le_gabarit_imprime_le_modele_definitif():
    env = Environment(loader=FileSystemLoader(str(TEMPLATES)), autoescape=select_autoescape())
    html = env.get_template("template_bulletin.html").render(vue=construire_vue_bulletin(_bulletin()))
    assert "REMBOURSEMENTS ET DÉDUCTIONS DIVERSES" in html
    assert "MONTANT NET A PAYER (en Euros)" in html
    assert html.index("MONTANT NET SOCIAL") < html.index("REMBOURSEMENTS ET DÉDUCTIONS DIVERSES")
