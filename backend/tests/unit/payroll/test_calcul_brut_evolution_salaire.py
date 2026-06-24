"""Tests calcul brut — évolution salaire (prorata + rappel)."""

from datetime import date

import pytest

from app.modules.payroll.engine.calcul_brut import (
    _construire_ligne_avantages_en_nature,
    calculer_salaire_brut,
)
from app.modules.payroll.engine.salary_evolution_brut import lignes_rappel_salaire

from .helpers import build_test_contexte

pytestmark = pytest.mark.unit


def _calendrier_travail_mois(year: int, month: int) -> list:
    import calendar

    last = calendar.monthrange(year, month)[1]
    return [
        {
            "date_complete": date(year, month, d).isoformat(),
            "type": "travail_base",
            "heures": 7.0,
        }
        for d in range(1, last + 1)
        if date(year, month, d).weekday() < 5
    ]


def test_prorata_mi_mois_juin():
    montant = round((2600 * 8 / 30) + (2678 * 22 / 30), 2)
    ctx = build_test_contexte(salaire_base=montant)
    ctx.contrat.setdefault("remuneration", {})["evolution_salaire_mois"] = {
        "salaire_debut_mois": 2600.0,
        "salaire_fin_mois": 2678.0,
        "prorata": {
            "ancien": 2600.0,
            "nouveau": 2678.0,
            "jours_ancien": 8,
            "jours_nouveau": 22,
            "montant_mois": montant,
        },
        "rappel": {"montant": 0.0, "periode_debut": None, "periode_fin": None},
    }

    debut = date(2026, 6, 1)
    fin = date(2026, 6, 30)
    res = calculer_salaire_brut(ctx, _calendrier_travail_mois(2026, 6), debut, fin)

    ligne_base = next(
        (
            l
            for l in res["lignes_composants_brut"]
            if (l.get("libelle") or "").startswith("Salaire de base")
        ),
        None,
    )
    assert ligne_base is not None
    assert ligne_base["gain"] == pytest.approx(montant, abs=0.05)


def test_ligne_rappel_salaire():
    ctx = build_test_contexte(salaire_base=2200.0)
    ctx.contrat.setdefault("remuneration", {})["evolution_salaire_mois"] = {
        "rappel": {
            "montant": 600.0,
            "periode_debut": "2026-03-01",
            "periode_fin": "2026-05-31",
        },
    }
    lignes = lignes_rappel_salaire(ctx)
    assert len(lignes) == 1
    assert lignes[0]["gain"] == 600.0
    assert "Rappel de salaire" in lignes[0]["libelle"]
    assert "2026-03-01" in lignes[0]["libelle"]


def test_rappel_inclus_dans_brut_total():
    ctx = build_test_contexte(salaire_base=2200.0)
    ctx.contrat.setdefault("remuneration", {})["evolution_salaire_mois"] = {
        "rappel": {
            "montant": 200.0,
            "periode_debut": "2026-05-01",
            "periode_fin": "2026-05-31",
        },
    }
    debut = date(2026, 6, 1)
    fin = date(2026, 6, 30)
    res = calculer_salaire_brut(ctx, _calendrier_travail_mois(2026, 6), debut, fin)
    rappel_lignes = [
        l for l in res["lignes_composants_brut"] if "Rappel" in (l.get("libelle") or "")
    ]
    assert len(rappel_lignes) == 1
    assert res["salaire_brut_total"] >= 2200.0 + 200.0 - 1


def test_avantages_en_nature_null_dans_contrat():
    ctx = build_test_contexte()
    ctx.contrat.setdefault("remuneration", {})["avantages_en_nature"] = None
    assert _construire_ligne_avantages_en_nature(ctx) is None
