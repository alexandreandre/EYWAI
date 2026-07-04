"""Tests HS conjoncturelles déclarées via saisie mensuelle."""

from datetime import date

import pytest

from app.modules.payroll.engine.calcul_brut import calculer_salaire_brut
from tests.unit.payroll.helpers import build_test_contexte

pytestmark = pytest.mark.unit


def test_hs_conjoncturelles_declarees_remplacent_calendrier():
    ctx = build_test_contexte(salaire_base=2165.85, duree_hebdo=39.0)
    ctx.contrat["specificites_paie"] = {"salaire_hors_hs_structurelles": True}
    ctx.contrat["saisie_du_mois"] = {
        "heures_supplementaires_conjoncturelles": 15.0,
    }
    ctx.baremes.setdefault("heures_supp", {}).setdefault(
        "regles_calcul_communes", {}
    ).setdefault("taux_majoration_par_defaut", {})["heures_supplementaires"] = [
        {"taux": 0.25},
        {"taux": 0.50},
    ]

    calendrier = [
        {
            "date_complete": "2026-05-12",
            "type": "travail_hs25",
            "heures": 4.0,
        },
        {
            "date_complete": "2026-05-13",
            "type": "travail_hs50",
            "heures": 5.0,
        },
    ]
    debut, fin = date(2026, 5, 1), date(2026, 5, 31)
    result = calculer_salaire_brut(ctx, calendrier, debut, fin)

    hs25 = next(
        l
        for l in result["lignes_composants_brut"]
        if l.get("libelle", "").startswith("Heures suppl. majorées à 25")
    )
    assert hs25["quantite"] == 15.0
    assert not any(
        "50" in l.get("libelle", "")
        for l in result["lignes_composants_brut"]
        if "Heures suppl." in l.get("libelle", "")
    )
