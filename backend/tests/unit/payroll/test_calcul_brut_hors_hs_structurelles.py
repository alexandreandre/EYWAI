"""Tests présentation salaire hors HS structurelles (base 151,67 h)."""

from datetime import date

import pytest

from app.modules.payroll.engine.calcul_brut import calculer_salaire_brut
from tests.unit.payroll.helpers import build_test_contexte

pytestmark = pytest.mark.unit


def test_contractuel_hors_hs_structurelles_39h():
    ctx = build_test_contexte(salaire_base=2165.85, duree_hebdo=39.0)
    ctx.contrat["specificites_paie"] = {"salaire_hors_hs_structurelles": True}
    ctx.baremes.setdefault("heures_supp", {}).setdefault(
        "regles_calcul_communes", {}
    ).setdefault("taux_majoration_par_defaut", {})["heures_supplementaires"] = [
        {"taux": 0.25},
        {"taux": 0.50},
    ]

    debut, fin = date(2026, 5, 1), date(2026, 5, 31)
    result = calculer_salaire_brut(ctx, [], debut, fin)
    lines = {l["libelle"]: l for l in result["lignes_composants_brut"]}

    base = lines["Salaire de base"]
    assert base["quantite"] == 151.67
    assert base["gain"] == 2165.85
    assert round(base["taux"], 2) == 14.28

    struct = next(
        l
        for l in result["lignes_composants_brut"]
        if "structurelles" in l["libelle"]
    )
    assert struct["quantite"] == 17.33
    assert struct["gain"] == 309.34

    sous_total = lines["SOUS-TOTAL SALAIRE CONTRACTUEL"]
    assert sous_total["gain"] == 2475.19
