"""Jour École (payé, hors entreprise) et congé sans solde (retenu même à 0 h)."""

from app.modules.payroll.application.analyzer import analyser_horaires_du_mois
from app.modules.payroll.documents.payslip_run_heures import TYPES_JOURS_COUVERTS
from app.modules.payroll.engine.calcul_brut import _est_une_absence
from app.shared.domain.absence_calendar import (
    ABSENCE_CALENDAR_TYPES,
    ABSENCE_TYPE_TO_CALENDAR_TYPE,
)


def _jour(type_jour: str, heures: float = 0.0) -> dict:
    return {
        "annee": 2026,
        "mois": 6,
        "jour": 2,
        "type": type_jour,
        "heures_prevues": heures,
    }


def test_sans_solde_ecrit_une_absence_non_remuneree():
    assert ABSENCE_TYPE_TO_CALENDAR_TYPE["sans_solde"] == "absence_non_remuneree"
    assert "absence_non_remuneree" in ABSENCE_CALENDAR_TYPES


def test_absence_non_remuneree_a_zero_heure_atteint_le_bulletin():
    evenements = analyser_horaires_du_mois([_jour("absence_non_remuneree")], [], 39, 2026, 6, "t")
    retenus = [e for e in evenements if e["type"] == "absence_non_remuneree"]
    assert len(retenus) == 1
    assert retenus[0]["jour"] == 2
    assert retenus[0]["heures"] == 0


def test_ecole_nest_pas_une_absence_et_ne_cree_pas_de_retenue():
    assert _est_une_absence("ecole") is False
    assert "ecole" in TYPES_JOURS_COUVERTS
    evenements = analyser_horaires_du_mois([_jour("ecole")], [], 39, 2026, 6, "t")
    assert not any(e.get("type") == "ecole" for e in evenements)
