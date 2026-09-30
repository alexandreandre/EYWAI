"""Import des pointages : les jours importés qui tombent sur un arrêt sont signalés.

Des heures importées un jour d'arrêt ou d'absence non travaillée sont celles
qui, le 30/09/2026, sont devenues 70,75 h sup pour une salariée arrêtée tout
septembre. L'import n'est pas bloqué : la réponse porte `jours_en_conflit`
(`[{employee_id, jours: [{annee, mois, jour, heures}]}]`), le résumé du lot
aussi, pour que le récapitulatif les montre. Supabase est moqué.
"""

from __future__ import annotations

from datetime import date
from unittest.mock import patch

import pytest

from app.modules.schedules.schemas.ai import (
    AiCalendarProposalResponse,
    AiDayEntry,
    AiEmployeeProposal,
)
from app.modules.schedules.schemas.persist import (
    PersistTimesheetEmployee,
    PersistTimesheetRequest,
)
from app.modules.schedules.schemas.timesheet_import import (
    TimesheetImportBatchSummary,
    TimesheetImportCommitRequest,
)

pytestmark = pytest.mark.unit

SERVICE = "app.modules.schedules.application.timesheet_import.commit_service"


def _ligne(prevu: list[dict], reel: list[dict] | None = None) -> dict:
    return {
        "employee_id": "e1",
        "company_id": "c1",
        "planned_calendar": {"calendrier_prevu": prevu},
        "actual_hours": {"calendrier_reel": reel or []},
    }


def _septembre() -> dict:
    """Arrêt les 7 et 8 septembre, travail le 9 ; le 8 portait déjà des heures."""
    return _ligne(
        [
            {"jour": 7, "type": "arret_maladie", "heures_prevues": 0, "origine": "absence"},
            {"jour": 8, "type": "arret_maladie", "heures_prevues": 0, "origine": "absence"},
            {"jour": 9, "type": "travail", "heures_prevues": 7.0},
        ],
        [{"jour": 8, "type": "travail", "heures_faites": 8.0}],
    )


def _lot(days: list[AiDayEntry], *, month: int = 9) -> dict:
    return {
        "id": "b-1",
        "company_id": "c1",
        "status": "previewed",
        "file_hash": "h-1",
        "preview_json": AiCalendarProposalResponse(
            year=2026,
            month=month,
            source="test",
            employees=[
                AiEmployeeProposal(
                    raw_name="SALARIEE",
                    employee_id="e1",
                    days=days,
                    review_status="ok",
                    match_confidence="high",
                )
            ],
        ).model_dump(mode="json"),
        "summary_json": {},
    }


def _commit(batch_id: str = "b-1"):
    from app.modules.schedules.application.timesheet_import.commit_service import (
        commit_batch_bulk,
    )

    return commit_batch_bulk(
        batch_id, company_id="c1", request=TimesheetImportCommitRequest()
    )


def _resume_final(mock_repo) -> dict:
    appel = next(
        a
        for a in mock_repo.update_batch.call_args_list
        if (a.args[1].get("status") == "committed")
    )
    return appel.args[1]["summary_json"]


@patch(f"{SERVICE}.record_schedule_import_run")
@patch(f"{SERVICE}.schedule_repository")
@patch(f"{SERVICE}.timesheet_import_repository")
@patch(f"{SERVICE}.get_employee_company_and_statut")
def test_un_jour_importe_sur_un_arret_est_signale_sans_bloquer_l_import(
    mock_statut, mock_repo, mock_sched, _audit
):
    mock_repo.get_batch.return_value = _lot(
        [
            AiDayEntry(jour=7, heures=9.0, type="travail", nature="reel"),
            AiDayEntry(jour=9, heures=7.0, type="travail", nature="reel"),
        ]
    )
    mock_statut.return_value = ("c1", "CDI")
    mock_sched.list_schedules_for_employees.return_value = {"e1": _septembre()}

    result = _commit()

    attendu = [
        {"employee_id": "e1", "jours": [{"annee": 2026, "mois": 9, "jour": 7, "heures": 9.0}]}
    ]
    # Le 8 portait déjà des heures, mais ne vient pas de cet import : pas signalé ici
    # (la génération, elle, le refusera).
    assert result["jours_en_conflit"] == attendu
    assert _resume_final(mock_repo)["commit_jours_en_conflit"] == attendu
    ecrits = {
        d["jour"]: d["heures_faites"]
        for appel in mock_sched.bulk_upsert_schedules.call_args_list
        for p in appel.args[0]
        for d in p["actual_hours"]["calendrier_reel"]
    }
    assert ecrits[7] == 9.0
    assert result["total_days_written"] == 2


@patch(f"{SERVICE}.record_schedule_import_run")
@patch(f"{SERVICE}.schedule_repository")
@patch(f"{SERVICE}.timesheet_import_repository")
@patch(f"{SERVICE}.get_employee_company_and_statut")
def test_un_import_sans_conflit_rend_une_liste_vide(
    mock_statut, mock_repo, mock_sched, _audit
):
    mock_repo.get_batch.return_value = _lot(
        [
            AiDayEntry(jour=7, heures=0.0, type="travail", nature="reel"),
            AiDayEntry(jour=9, heures=7.0, type="travail", nature="reel"),
        ]
    )
    mock_statut.return_value = ("c1", "CDI")
    mock_sched.list_schedules_for_employees.return_value = {"e1": _septembre()}

    result = _commit()

    assert result["jours_en_conflit"] == []


@patch(f"{SERVICE}.record_schedule_import_run")
@patch(f"{SERVICE}.schedule_repository")
@patch(f"{SERVICE}.timesheet_import_repository")
@patch(f"{SERVICE}.get_employee_company_and_statut")
def test_une_semaine_a_cheval_nomme_chaque_mois_pour_un_meme_salarie(
    mock_statut, mock_repo, mock_sched, _audit
):
    """S27 : le 30 juin est un jour d'arrêt, le 1er juillet aussi."""
    mock_repo.get_batch.return_value = _lot(
        [
            AiDayEntry(jour=30, heures=8.0, type="travail", nature="reel", year=2026, month=6),
            AiDayEntry(jour=1, heures=7.5, type="travail", nature="reel"),
        ],
        month=7,
    )
    mock_statut.return_value = ("c1", "CDI")
    mock_sched.list_schedules_for_employees.side_effect = lambda ids, y, m: {
        "e1": _ligne([{"jour": 30 if m == 6 else 1, "type": "arret_maladie", "heures_prevues": 0}])
    }

    result = _commit()

    assert result["jours_en_conflit"] == [
        {
            "employee_id": "e1",
            "jours": [
                {"annee": 2026, "mois": 6, "jour": 30, "heures": 8.0},
                {"annee": 2026, "mois": 7, "jour": 1, "heures": 7.5},
            ],
        }
    ]


@patch(f"{SERVICE}.record_schedule_import_run")
@patch(f"{SERVICE}.admin_repo")
@patch(f"{SERVICE}.schedule_repository")
@patch(f"{SERVICE}.timesheet_import_repository")
def test_le_lot_multi_mois_signale_aussi(mock_repo, mock_sched, mock_admin, _audit):
    lot = _lot([], month=9)
    lot["summary_json"] = {
        "multi_month": True,
        "month_groups": [
            {
                "year": 2026,
                "month": 9,
                "employees": [
                    {
                        "employee_id": "e1",
                        "raw_name": "SALARIEE",
                        "days": [
                            {"jour": 7, "heures": 9.0, "type": "travail", "nature": "reel"}
                        ],
                    }
                ],
            }
        ],
    }
    mock_repo.get_batch.return_value = lot
    mock_repo.is_cancel_requested.return_value = False
    mock_admin.list_company_employees.return_value = [{"id": "e1", "company_id": "c1"}]
    mock_sched.list_schedules_for_employees.return_value = {"e1": _septembre()}

    result = _commit()

    attendu = [
        {"employee_id": "e1", "jours": [{"annee": 2026, "mois": 9, "jour": 7, "heures": 9.0}]}
    ]
    assert result["jours_en_conflit"] == attendu
    assert _resume_final(mock_repo)["commit_jours_en_conflit"] == attendu


@patch(f"{SERVICE}.arrets_valides_reader")
@patch(f"{SERVICE}.record_schedule_import_run")
@patch(f"{SERVICE}.schedule_repository")
@patch(f"{SERVICE}.timesheet_import_repository")
@patch(f"{SERVICE}.get_employee_company_and_statut")
def test_un_samedi_d_arret_valide_importe_est_signale(
    mock_statut, mock_repo, mock_sched, _audit, mock_arrets
):
    ligne = _septembre()
    ligne["planned_calendar"]["calendrier_prevu"].append(
        {"jour": 12, "type": "weekend", "heures_prevues": 0}
    )
    mock_repo.get_batch.return_value = _lot(
        [AiDayEntry(jour=12, heures=5.0, type="travail", nature="reel")]
    )
    mock_statut.return_value = ("c1", "CDI")
    mock_sched.list_schedules_for_employees.return_value = {"e1": ligne}
    mock_arrets.par_salarie.return_value = {
        "e1": [{"type": "arret_maladie", "status": "validated", "selected_days": ["2026-09-12"]}]
    }

    result = _commit()

    mock_arrets.par_salarie.assert_called_once_with(["e1"], date(2026, 9, 1), date(2026, 9, 30))
    assert result["jours_en_conflit"] == [
        {"employee_id": "e1", "jours": [{"annee": 2026, "mois": 9, "jour": 12, "heures": 5.0}]}
    ]


@patch(f"{SERVICE}.logger")
@patch(f"{SERVICE}.arrets_valides_reader")
@patch(f"{SERVICE}.record_schedule_import_run")
@patch(f"{SERVICE}.schedule_repository")
@patch(f"{SERVICE}.timesheet_import_repository")
@patch(f"{SERVICE}.get_employee_company_and_statut")
def test_des_arrets_illisibles_n_empechent_pas_l_import(
    mock_statut, mock_repo, mock_sched, _audit, mock_arrets, mock_log
):
    """L'import écrit quand même ; il signale ce que le type prévu suffit à voir."""
    mock_repo.get_batch.return_value = _lot(
        [AiDayEntry(jour=7, heures=9.0, type="travail", nature="reel")]
    )
    mock_statut.return_value = ("c1", "CDI")
    mock_sched.list_schedules_for_employees.return_value = {"e1": _septembre()}
    mock_arrets.par_salarie.side_effect = RuntimeError("réseau")

    result = _commit()

    mock_sched.bulk_upsert_schedules.assert_called_once()
    assert result["jours_en_conflit"] == [
        {"employee_id": "e1", "jours": [{"annee": 2026, "mois": 9, "jour": 7, "heures": 9.0}]}
    ]
    mock_log.warning.assert_called_once()


def test_la_reponse_de_persist_timesheet_porte_les_jours_en_conflit():
    from app.modules.schedules.application.persist_timesheet import (
        run_persist_with_bulk_commit,
    )

    jours = [
        {"employee_id": "e1", "jours": [{"annee": 2026, "mois": 9, "jour": 7, "heures": 9.0}]}
    ]
    payload = PersistTimesheetRequest(
        year=2026,
        month=9,
        employees=[
            PersistTimesheetEmployee(
                employee_id="e1",
                days=[AiDayEntry(jour=7, heures=9.0, type="travail", nature="reel")],
            )
        ],
    )
    with patch(
        f"{SERVICE}.commit_from_persist_request",
        return_value={
            "employees_processed": 1,
            "total_days_written": 1,
            "errors": [],
            "warnings": [],
            "jours_en_conflit": jours,
        },
    ):
        reponse = run_persist_with_bulk_commit(payload, company_id="c1", user_id="u1")

    assert reponse.model_dump()["jours_en_conflit"] == jours


def test_le_resume_du_lot_garde_les_jours_en_conflit():
    """Sans le champ, Pydantic le retire et le récapitulatif ne le voit jamais."""
    jours = [{"employee_id": "e1", "jours": [{"annee": 2026, "mois": 9, "jour": 7, "heures": 9.0}]}]

    resume = TimesheetImportBatchSummary(committed_days=1, commit_jours_en_conflit=jours)

    assert resume.model_dump()["commit_jours_en_conflit"] == jours
