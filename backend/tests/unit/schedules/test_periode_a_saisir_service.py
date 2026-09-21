"""Le service charge la fenêtre du moteur, les plannings des mois couverts et le
contrat, puis délègue au domaine. Supabase est moqué : on vérifie ce qu'il lit."""

from __future__ import annotations

from datetime import date
from unittest.mock import patch

import pytest

from app.shared.domain.periode_variables import FenetreVariables

pytestmark = pytest.mark.unit

SERVICE = "app.modules.schedules.application.periode_a_saisir_service"
FENETRE_JUILLET = FenetreVariables(debut=date(2026, 6, 22), fin=date(2026, 7, 26), origine="regle")


def _ligne(prevu, reel):
    return {"planned_calendar": {"calendrier_prevu": prevu}, "actual_hours": {"calendrier_reel": reel}}


def _juillet_saisi_jusqu_au_24():
    prevu = [
        {
            "jour": j,
            "type": "travail" if date(2026, 7, j).weekday() < 5 else "repos",
            "heures_prevues": 8.0 if date(2026, 7, j).weekday() < 5 else 0.0,
        }
        for j in range(1, 32)
    ]
    reel = [{"jour": j, "heures_faites": 8.0} for j in range(1, 25) if date(2026, 7, j).weekday() < 5]
    return _ligne(prevu, reel)


@patch(f"{SERVICE}.schedule_repository")
@patch(f"{SERVICE}.resoudre_fenetre_variables", return_value=FENETRE_JUILLET)
def test_lit_les_deux_mois_couverts_par_l_union(mock_fenetre, mock_repo):
    from app.modules.schedules.application.periode_a_saisir_service import (
        charger_periodes_a_saisir,
    )

    mock_repo.list_schedules_for_employees.side_effect = lambda ids, y, m: (
        {"e1": _juillet_saisi_jusqu_au_24()} if (y, m) == (2026, 7) else {}
    )
    employes = [{"id": "e1", "statut": "Non-Cadre", "is_forfait_jour": False, "hire_date": "2020-01-15"}]

    periodes = charger_periodes_a_saisir("c1", employes, 2026, 7)

    mois_lus = sorted(
        (appel.args[1], appel.args[2]) for appel in mock_repo.list_schedules_for_employees.call_args_list
    )
    assert mois_lus == [(2026, 6), (2026, 7)]
    mock_fenetre.assert_called_once_with("c1", 2026, 7)
    periode = periodes["e1"]
    assert periode.statut == "a_saisir"
    assert [j.jour.isoformat() for j in periode.bloquants][:2] == ["2026-06-22", "2026-06-23"]
    assert [j.jour.day for j in periode.informatifs] == [27, 28, 29, 30, 31]


@patch(f"{SERVICE}.schedule_repository")
@patch(f"{SERVICE}.resoudre_fenetre_variables", return_value=FENETRE_JUILLET)
def test_les_bornes_du_contrat_viennent_de_la_fiche(mock_fenetre, mock_repo):
    from app.modules.schedules.application.periode_a_saisir_service import (
        charger_periode_a_saisir,
    )

    mock_repo.list_schedules_for_employees.return_value = {}
    employe = {
        "id": "e1",
        "statut": "Non-Cadre",
        "hire_date": "2026-07-06",
        "exit_last_working_day": "2026-07-15",
    }

    periode = charger_periode_a_saisir("c1", employe, 2026, 7)

    jours = [j.jour for j in periode.manquants]
    assert min(jours) == date(2026, 7, 6) and max(jours) == date(2026, 7, 15)


@patch(f"{SERVICE}.schedule_repository")
@patch(f"{SERVICE}.resoudre_fenetre_variables", return_value=FENETRE_JUILLET)
def test_resume_api_expose_fenetre_et_dates(mock_fenetre, mock_repo):
    from app.modules.schedules.application.periode_a_saisir_service import (
        charger_periode_a_saisir,
        resume_api,
    )

    mock_repo.list_schedules_for_employees.side_effect = lambda ids, y, m: (
        {"e1": _juillet_saisi_jusqu_au_24()} if (y, m) == (2026, 7) else {}
    )

    resume = resume_api(charger_periode_a_saisir("c1", {"id": "e1", "statut": "Non-Cadre"}, 2026, 7))

    assert resume["fenetre"] == {
        "debut": "2026-06-22",
        "fin": "2026-07-26",
        "semaines": [26, 27, 28, 29, 30],
        "origine": "regle",
    }
    assert resume["jours_manquants"][:2] == ["2026-06-22", "2026-06-23"]
    assert resume["jours_informatifs"] == [
        "2026-07-27",
        "2026-07-28",
        "2026-07-29",
        "2026-07-30",
        "2026-07-31",
    ]
