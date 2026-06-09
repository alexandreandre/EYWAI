"""Heures complémentaires temps partiel : qualification, majoration, prorata PSS."""

from __future__ import annotations

from datetime import date

import pytest

from app.modules.payroll.application.analyzer import analyser_horaires_du_mois
from app.modules.payroll.engine.calcul_brut import calculer_salaire_brut
from app.modules.payroll.engine.calcul_cotisations import _calculer_assiettes

from .helpers import build_test_contexte


def _ctx_temps_partiel(duree_hebdo: float = 24.0, salaire: float = 1500.0):
    return build_test_contexte(
        salaire_base=salaire,
        duree_hebdo=duree_hebdo,
        type_contrat="CDI",
        is_temps_partiel=True,
        proratiser_plafond_ss=True,
    )


def test_hc_majorees_ajoutees_au_brut():
    ctx = _ctx_temps_partiel()
    cal = [
        {"date_complete": "2026-03-10", "type": "travail_hc10", "heures": 8.0},
        {"date_complete": "2026-03-12", "type": "travail_hc25", "heures": 4.0},
    ]
    res = calculer_salaire_brut(ctx, cal, date(2026, 3, 1), date(2026, 3, 31), [])
    libelles = [
        l["libelle"] for l in res["lignes_composants_brut"] if l.get("gain")
    ]
    assert any("Heures complémentaires majorées à 10%" in lib for lib in libelles)
    assert any("Heures complémentaires majorées à 25%" in lib for lib in libelles)
    assert res["heures_complementaires"] == pytest.approx(12.0)
    # taux horaire = 1500 / (24*52/12=104) ; HC10 = 8*taux*1.1, HC25 = 4*taux*1.25
    taux = 1500.0 / 104.0
    attendu = 1500.0 + 8 * taux * 1.10 + 4 * taux * 1.25
    assert res["salaire_brut_total"] == pytest.approx(round(attendu, 2), abs=0.05)


def test_hc_relevent_le_prorata_pss():
    ctx = _ctx_temps_partiel()
    # Sans HC : prorata = 24/35.
    assiettes_sans = _calculer_assiettes(ctx, 1500.0, 0.0)
    ctx2 = _ctx_temps_partiel()
    cal = [{"date_complete": "2026-03-10", "type": "travail_hc10", "heures": 20.0}]
    calculer_salaire_brut(ctx2, cal, date(2026, 3, 1), date(2026, 3, 31), [])
    assiettes_avec = _calculer_assiettes(ctx2, 1500.0, 0.0)
    assert assiettes_avec["plafond_ss"] > assiettes_sans["plafond_ss"]


def test_analyzer_qualifie_les_hc_temps_partiel():
    # 24h contractuelles ; semaine du 2 au 6 mars 2026 à 6h/j = 30h -> 6h HC.
    prevu = [
        {"annee": 2026, "mois": 3, "jour": d, "type": "travail", "heures_prevues": 4.8}
        for d in [2, 3, 4, 5, 6]
    ]
    reel = [
        {"annee": 2026, "mois": 3, "jour": d, "type": "reel", "heures_faites": 6.0}
        for d in [2, 3, 4, 5, 6]
    ]
    ev = analyser_horaires_du_mois(prevu, reel, 24.0, 2026, 3, "x")
    types = {e["type"]: e["heures"] for e in ev if "hc" in e["type"]}
    assert "travail_hc10" in types
    assert "travail_hc25" in types
    assert types["travail_hc10"] + types["travail_hc25"] == pytest.approx(6.0, abs=0.05)


def test_analyzer_repli_planning_sans_pointage():
    prevu = [
        {"annee": 2026, "mois": 6, "jour": 2, "type": "travail", "heures_prevues": 7.0},
        {"annee": 2026, "mois": 6, "jour": 3, "type": "travail", "heures_prevues": 7.0},
    ]
    ev = analyser_horaires_du_mois(prevu, [], 35.0, 2026, 6, "x")
    types = [e["type"] for e in ev]
    # Sans pointage, le repli planning évite les absences fictives.
    # Les heures normales (sans HS/HC) ne produisent pas d'événement : le salaire
    # de base est versé tel quel dans calcul_brut.
    assert "absence_injustifiee_base" not in types
    assert not any(t.startswith("absence") for t in types)
