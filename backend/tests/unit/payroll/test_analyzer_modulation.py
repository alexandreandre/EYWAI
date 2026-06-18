"""Tests analyseur paie avec modulation hebdomadaire."""

from app.modules.payroll.application.analyzer import analyser_horaires_du_mois


def _work_day(jour: int, heures: float) -> dict:
    return {"annee": 2026, "mois": 3, "jour": jour, "heures_faites": heures}


def test_modulation_low_week_reduces_hs_threshold():
    """Semaine 32h : 36h travaillées → moins de HS qu'en 35h."""
    reel = [_work_day(d, 7.2) for d in range(3, 8)]  # lun–ven ≈ 36h
    prevu = []
    mod_map = {(2026, 10): 32.0}
    ev_mod = analyser_horaires_du_mois(
        prevu, reel, 35.0, 2026, 3, "test", modulation_weekly_hours=mod_map
    )
    ev_std = analyser_horaires_du_mois(prevu, reel, 35.0, 2026, 3, "test")
    hs_mod = sum(e.get("heures", 0) for e in ev_mod if "hs" in e.get("type", ""))
    hs_std = sum(e.get("heures", 0) for e in ev_std if "hs" in e.get("type", ""))
    assert hs_mod >= hs_std
