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


# --- Déclaration faite depuis le bulletin : elle fait foi (audit du 28/09) ---

CALENDRIER_4_25_5_50 = [
    {"date_complete": "2026-05-12", "type": "travail_hs25", "heures": 4.0},
    {"date_complete": "2026-05-13", "type": "travail_hs50", "heures": 5.0},
]


def _brut_avec(saisie):
    ctx = build_test_contexte(salaire_base=2165.85, duree_hebdo=39.0)
    ctx.contrat["specificites_paie"] = {"salaire_hors_hs_structurelles": True}
    ctx.contrat["saisie_du_mois"] = saisie
    ctx.baremes.setdefault("heures_supp", {}).setdefault(
        "regles_calcul_communes", {}
    ).setdefault("taux_majoration_par_defaut", {})["heures_supplementaires"] = [
        {"taux": 0.25},
        {"taux": 0.50},
    ]
    result = calculer_salaire_brut(
        ctx, CALENDRIER_4_25_5_50, date(2026, 5, 1), date(2026, 5, 31)
    )
    return ctx, result


def _quantite(result, palier):
    lignes = [
        l
        for l in result["lignes_composants_brut"]
        if l.get("libelle", "").startswith(f"Heures suppl. majorées à {palier}")
    ]
    return lignes[0]["quantite"] if lignes else 0.0


def test_une_declaration_bulletin_a_zero_retire_les_heures_du_planning():
    ctx, result = _brut_avec(
        {
            "heures_supplementaires_conjoncturelles": 0.0,
            "heures_supplementaires_conjoncturelles_50": 0.0,
            "heures_sup_declarees_au_bulletin": True,
        }
    )
    assert _quantite(result, 25) == 0.0 and _quantite(result, 50) == 0.0
    assert ctx.heures_sup_declarees == {"hs25": 0.0, "hs50": 0.0, "planning": 9.0}


def test_une_declaration_bulletin_de_meme_total_change_la_repartition():
    ctx, result = _brut_avec(
        {
            "heures_supplementaires_conjoncturelles": 9.0,
            "heures_supplementaires_conjoncturelles_50": 0.0,
            "heures_sup_declarees_au_bulletin": True,
        }
    )
    assert _quantite(result, 25) == 9.0 and _quantite(result, 50) == 0.0


def test_une_saisie_ordinaire_de_meme_total_garde_la_regle_actuelle():
    """Hors déclaration au bulletin, rien ne change : un total égal au planning
    laisse la répartition du planning."""
    ctx, result = _brut_avec(
        {
            "heures_supplementaires_conjoncturelles": 9.0,
            "heures_supplementaires_conjoncturelles_50": 0.0,
        }
    )
    assert _quantite(result, 25) == 4.0 and _quantite(result, 50) == 5.0
    assert getattr(ctx, "heures_sup_declarees", None) is None


def test_une_saisie_ordinaire_a_zero_n_efface_pas_le_planning():
    ctx, result = _brut_avec({"heures_supplementaires_conjoncturelles": 0.0})
    assert _quantite(result, 25) == 4.0 and _quantite(result, 50) == 5.0
