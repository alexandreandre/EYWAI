"""Le tableau de bord et la génération ne peuvent plus se contredire : même juge."""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from app.shared.domain.periode_variables import FenetreVariables

pytestmark = pytest.mark.unit

MODULE = "app.modules.dashboard.application.analytics_gestion"
SERVICE = "app.modules.schedules.application.periode_a_saisir_service"


def _mois(annee: int, mois: int, *, reel_jusqu_au: int, employee_id: str = "e1"):
    import calendar

    prevu, reel = [], []
    for j in range(1, calendar.monthrange(annee, mois)[1] + 1):
        ouvre = date(annee, mois, j).weekday() < 5
        prevu.append(
            {"jour": j, "type": "travail" if ouvre else "repos", "heures_prevues": 8.0 if ouvre else 0.0}
        )
        if ouvre and j <= reel_jusqu_au:
            reel.append({"jour": j, "heures_faites": 8.0})
    return {
        "employee_id": employee_id,
        "planned_calendar": {"calendrier_prevu": prevu},
        "actual_hours": {"calendrier_reel": reel},
    }


def _supabase(schedules):
    sb = MagicMock()
    employes = MagicMock()
    employes.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[{"id": "e1", "statut": "Non-Cadre", "is_forfait_jour": False}]
    )
    plannings = MagicMock()
    plannings.select.return_value.eq.return_value.eq.return_value.eq.return_value.in_.return_value.execute.return_value = MagicMock(
        data=schedules
    )
    sb.table.side_effect = lambda name: employes if name == "employees" else plannings
    return sb


@patch(f"{SERVICE}.schedule_repository")
@patch(f"{SERVICE}.resoudre_fenetre_variables")
def test_juillet_saisi_jusqu_au_24_est_saisi_si_la_fenetre_s_arrete_au_26(mock_fenetre, mock_repo):
    from app.modules.dashboard.application.analytics_gestion import _build_calendriers_overview

    juillet = _mois(2026, 7, reel_jusqu_au=24)
    juin = _mois(2026, 6, reel_jusqu_au=30)
    mock_fenetre.return_value = FenetreVariables(debut=date(2026, 6, 22), fin=date(2026, 7, 26), origine="regle")
    mock_repo.list_schedules_for_employees.side_effect = lambda ids, y, m: {"e1": juillet if m == 7 else juin}

    with patch(f"{MODULE}.supabase", _supabase([juillet])), patch(
        "app.modules.absences.infrastructure.repository.absence_repository.list_validated_for_employees",
        return_value=[],
    ):
        overview = _build_calendriers_overview("c1", 2026, 7)

    assert (overview.saisis, overview.a_saisir) == (1, 0)
