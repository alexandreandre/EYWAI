"""Plafond de la Sécurité sociale : réduction prorata temporis (entrée/sortie,
absences non rémunérées) et régularisation progressive de la tranche 1.

Valeurs de référence : bulletins du cabinet (Cegid) MAJI / ZONE 404 2026.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.modules.payroll.engine.calcul_cotisations import (
    _calculer_assiettes,
    ratio_plafond_periode,
)

from .helpers import build_test_contexte

pytestmark = pytest.mark.unit


def _ev(jour: str, type_ev: str = "arret_maladie") -> dict:
    return {"date_complete": jour, "type": type_ev, "heures": 0.0}


def test_ratio_entree_en_cours_de_mois_en_jours_calendaires():
    # ASSANHAJI Zone 404, entré le 05/01/2026 : plafond 4 005 × 27/31 = 3 488,23.
    ctx = build_test_contexte(date_entree="2026-01-05")
    ratio = ratio_plafond_periode([], date(2026, 1, 1), date(2026, 1, 31), ctx)
    assert ratio == pytest.approx(27 / 31, abs=1e-6)


def test_ratio_arret_sans_ponter_le_samedi_en_bord_de_mois():
    # ANDRE MAJI 01/2026 : arrêt jeudi 29 et vendredi 30 → 29/31, le samedi 31
    # n'est pas compté (aucune absence après).
    ctx = build_test_contexte()
    cal = [_ev("2026-01-29"), _ev("2026-01-30")]
    ratio = ratio_plafond_periode(cal, date(2026, 1, 1), date(2026, 1, 31), ctx)
    assert ratio == pytest.approx(29 / 31, abs=1e-6)


def test_ratio_arret_pontant_le_week_end_et_le_ferie():
    # ANDRE MAJI 04/2026 : arrêt du 01 au 10/04 (week-end 4-5 et lundi de Pâques
    # 6 encadrés par des jours d'arrêt) → 10 jours calendaires → 20/30.
    ctx = build_test_contexte()
    cal = [_ev(f"2026-04-{d:02d}") for d in (1, 2, 3, 7, 8, 9, 10)]
    cal.append({"date_complete": "2026-04-06", "type": "ferie", "heures": 0.0})
    ratio = ratio_plafond_periode(cal, date(2026, 4, 1), date(2026, 4, 30), ctx)
    assert ratio == pytest.approx(20 / 30, abs=1e-6)


def test_ratio_mois_entier_absent_vaut_zero():
    ctx = build_test_contexte()
    cal = [
        _ev(date(2026, 2, d).isoformat())
        for d in range(1, 29)
        if date(2026, 2, d).weekday() < 5
    ]
    assert ratio_plafond_periode(cal, date(2026, 2, 1), date(2026, 2, 28), ctx) == 0.0


def test_ratio_ferie_non_paye_compte_comme_absence():
    # BARAN Zone 404, entré le 05/03 : lundi de Pâques 06/04 non payé → 29/30.
    ctx = build_test_contexte(date_entree="2026-03-05", prior_service_months=0)
    cal = [{"date_complete": "2026-04-06", "type": "ferie", "heures": 0.0}]
    ratio = ratio_plafond_periode(cal, date(2026, 4, 1), date(2026, 4, 30), ctx)
    assert ratio == pytest.approx(29 / 30, abs=1e-6)


def test_ratio_ferie_paye_ne_reduit_pas():
    ctx = build_test_contexte(date_entree="2020-01-01")
    cal = [{"date_complete": "2026-04-06", "type": "ferie", "heures": 0.0}]
    assert ratio_plafond_periode(cal, date(2026, 4, 1), date(2026, 4, 30), ctx) == 1.0


def test_ratio_sans_absence_ni_entree_vaut_un():
    ctx = build_test_contexte()
    cal = [{"date_complete": "2026-03-10", "type": "conges_payes", "heures": 7.0}]
    assert ratio_plafond_periode(cal, date(2026, 3, 1), date(2026, 3, 31), ctx) == 1.0


def test_plafond_reduit_applique_aux_assiettes():
    ctx = build_test_contexte()
    ctx.ratio_plafond_ss = 27 / 31
    assiettes = _calculer_assiettes(ctx, 3000.0, 0.0)
    pss = ctx.baremes["pss"]["mensuel"]
    assert assiettes["plafond_ss"] == pytest.approx(round(pss * 27 / 31, 2), abs=0.01)


def _cumuls(brut: float, pss: float, t1: float, t2: float = 0.0) -> dict:
    return {
        "cumul_brut_agirc_arrco": brut,
        "cumul_pss_agirc_arrco": pss,
        "cumul_tranche_1_appliquee": t1,
        "cumul_tranche_2_appliquee": t2,
    }


def test_tranche_1_reprend_le_plafond_inutilise_des_mois_precedents():
    # AGOUMBI Zone 404 05/2026 : 13 897,82 de brut cumulé pour 16 020 de plafond
    # cumulé ; le mois à 4 608 tient entièrement en tranche 1, pas de tranche 2,
    # pas de CET.
    ctx = build_test_contexte(cumuls=_cumuls(13897.82, 16020.0, 13897.82))
    ctx.month = 5
    assiettes = _calculer_assiettes(ctx, 4608.0, 0.0)
    assert assiettes["brut_plafonne"] == pytest.approx(4608.0, abs=0.01)
    assert assiettes["tranche_2"] == pytest.approx(0.0, abs=0.01)
    assert assiettes["assiette_cet"] == pytest.approx(0.0, abs=0.01)


def test_tranche_1_stable_sous_le_plafond_reste_le_brut():
    ctx = build_test_contexte(cumuls=_cumuls(12000.0, 16020.0, 12000.0))
    ctx.month = 5
    assiettes = _calculer_assiettes(ctx, 3000.0, 0.0)
    assert assiettes["brut_plafonne"] == pytest.approx(3000.0, abs=0.01)
    assert assiettes["tranche_2"] == pytest.approx(0.0, abs=0.01)


def test_tranche_1_stable_au_dessus_du_plafond_reste_le_plafond():
    pss = build_test_contexte().baremes["pss"]["mensuel"]
    ctx = build_test_contexte(
        cumuls=_cumuls(4 * 6000.0, 4 * pss, 4 * pss, 4 * (6000.0 - pss))
    )
    ctx.month = 5
    assiettes = _calculer_assiettes(ctx, 6000.0, 0.0)
    assert assiettes["brut_plafonne"] == pytest.approx(pss, abs=0.01)
    assert assiettes["tranche_2"] == pytest.approx(6000.0 - pss, abs=0.01)
    assert assiettes["assiette_cet"] > 0


def test_tranche_1_sans_cumuls_en_janvier_vaut_min_brut_plafond():
    pss = build_test_contexte().baremes["pss"]["mensuel"]
    ctx = build_test_contexte()
    ctx.month = 1
    assert _calculer_assiettes(ctx, 6000.0, 0.0)["brut_plafonne"] == pytest.approx(pss, abs=0.01)
    assert _calculer_assiettes(ctx, 3000.0, 0.0)["brut_plafonne"] == pytest.approx(3000.0, abs=0.01)
