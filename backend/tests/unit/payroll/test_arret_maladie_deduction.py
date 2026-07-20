"""Retenue d'un jour d'arrêt maladie : toujours valorisée sur la référence
journalière LÉGALE (7 h temps plein), jamais sur les heures planifiées du jour
(7,5 h contractuelles d'un template), sinon sur-déduction — la quote-part d'HS
structurelle est déjà retirée séparément (cf. OSMANI2 MBC mai 2026)."""

from datetime import date

import pytest

from app.modules.payroll.engine.calcul_brut import calculer_salaire_brut
from tests.unit.payroll.helpers import build_test_contexte

pytestmark = pytest.mark.unit


def _ctx_hors_hs():
    ctx = build_test_contexte(salaire_base=2165.85, duree_hebdo=37.5)
    ctx.contrat["specificites_paie"] = {"salaire_hors_hs_structurelles": True}
    ctx.baremes.setdefault("heures_supp", {}).setdefault(
        "regles_calcul_communes", {}
    ).setdefault("taux_majoration_par_defaut", {})["heures_supplementaires"] = [
        {"taux": 0.25},
        {"taux": 0.50},
    ]
    return ctx


def test_arret_maladie_journee_pleine_deduite_a_la_reference_legale():
    """Un jour d'arrêt planifié 7,5 h se déduit à 7 h (référence légale)."""
    ctx = _ctx_hors_hs()
    cal = [
        {"date_complete": "2026-05-04", "type": "arret_maladie",
         "heures": 7.5, "arret_type": "maladie_simple"},
    ]
    result = calculer_salaire_brut(ctx, cal, date(2026, 5, 1), date(2026, 5, 31))
    arret = next(
        l for l in result["lignes_composants_brut"] if l.get("is_arret_maladie")
    )
    # 7,0 h légales et non 7,5 h planifiées.
    assert arret["quantite"] == 7.0
    taux_base = arret["taux"]
    assert arret["perte"] == round(7.0 * taux_base, 2)


def test_arret_maladie_fractionnaire_preserve():
    """Un arrêt fractionnaire (demi-journée < réf. légale) garde ses heures réelles."""
    ctx = _ctx_hors_hs()
    cal = [
        {"date_complete": "2026-05-04", "type": "arret_maladie",
         "heures": 3.5, "arret_type": "maladie_simple"},
    ]
    result = calculer_salaire_brut(ctx, cal, date(2026, 5, 1), date(2026, 5, 31))
    arret = next(
        l for l in result["lignes_composants_brut"] if l.get("is_arret_maladie")
    )
    assert arret["quantite"] == 3.5
