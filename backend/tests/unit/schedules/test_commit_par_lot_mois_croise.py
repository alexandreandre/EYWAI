"""Commit par lot : semaine à cheval sur deux mois, heures négatives.

Constat du 19/09/2026 sur le test Colorplast : l'import S27 (29/06 → 05/07)
avait écrit les 29 et 30 juin sous les numéros 29 et 30 de juillet, et des
heures négatives (−10,5 h) étaient passées telles quelles dans le planning.
"""

from unittest.mock import patch

import pytest

from app.modules.schedules.application.exceptions import ScheduleAppError
from app.modules.schedules.application.persist_timesheet import validate_persist_payload
from app.modules.schedules.schemas.ai import (
    AiCalendarProposalResponse,
    AiDayEntry,
    AiEmployeeProposal,
)
from app.modules.schedules.schemas.persist import (
    PersistTimesheetEmployee,
    PersistTimesheetRequest,
)
from app.modules.schedules.schemas.timesheet_import import TimesheetImportCommitRequest

SERVICE = "app.modules.schedules.application.timesheet_import.commit_service"


def _lot_de_juillet(days: list[AiDayEntry]) -> dict:
    return {
        "id": "b-s27",
        "company_id": "c1",
        "status": "previewed",
        "file_hash": "h-s27",
        "preview_json": AiCalendarProposalResponse(
            year=2026,
            month=7,
            source="test",
            employees=[
                AiEmployeeProposal(
                    raw_name="BUGNY",
                    employee_id="e1",
                    days=days,
                    review_status="ok",
                    match_confidence="high",
                )
            ],
        ).model_dump(mode="json"),
        "summary_json": {},
    }


def _semaine_27() -> list[AiDayEntry]:
    return [
        AiDayEntry(
            jour=29, heures=8.0, type="travail", nature="reel", year=2026, month=6
        ),
        AiDayEntry(
            jour=30, heures=8.0, type="travail", nature="reel", year=2026, month=6
        ),
        AiDayEntry(jour=1, heures=7.5, type="travail", nature="reel"),
    ]


def _commit(batch_id: str, **kwargs):
    from app.modules.schedules.application.timesheet_import.commit_service import (
        commit_batch_bulk,
    )

    return commit_batch_bulk(
        batch_id,
        company_id="c1",
        request=TimesheetImportCommitRequest(**kwargs),
    )


@patch(f"{SERVICE}.record_schedule_import_run")
@patch(f"{SERVICE}.schedule_repository")
@patch(f"{SERVICE}.timesheet_import_repository")
@patch(f"{SERVICE}.get_employee_company_and_statut")
def test_les_jours_de_juin_d_une_semaine_27_sont_ecrits_en_juin(
    mock_statut, mock_repo, mock_sched, _audit
):
    mock_repo.get_batch.return_value = _lot_de_juillet(_semaine_27())
    mock_statut.return_value = ("c1", "CDI")
    mock_sched.list_schedules_for_employees.return_value = {}

    result = _commit("b-s27")

    assert result["total_days_written"] == 3
    mois_lus = [
        (appel.args[1], appel.args[2])
        for appel in mock_sched.list_schedules_for_employees.call_args_list
    ]
    assert mois_lus == [(2026, 6), (2026, 7)]
    ecrits = {
        (p["year"], p["month"]): sorted(
            d["jour"] for d in p["actual_hours"]["calendrier_reel"]
        )
        for appel in mock_sched.bulk_upsert_schedules.call_args_list
        for p in appel.args[0]
    }
    assert ecrits == {(2026, 6): [29, 30], (2026, 7): [1]}


@patch("app.modules.schedules.application.commands.calculate_payroll_events")
@patch(f"{SERVICE}.record_schedule_import_run")
@patch(f"{SERVICE}.schedule_repository")
@patch(f"{SERVICE}.timesheet_import_repository")
@patch(f"{SERVICE}.get_employee_company_and_statut")
def test_le_recalcul_de_paie_vise_chaque_mois_ecrit(
    mock_statut, mock_repo, mock_sched, _audit, mock_recalc
):
    mock_repo.get_batch.return_value = _lot_de_juillet(_semaine_27())
    mock_statut.return_value = ("c1", "CDI")
    mock_sched.list_schedules_for_employees.return_value = {}

    _commit("b-s27", recalculate_payroll=True)

    assert sorted(appel.args for appel in mock_recalc.call_args_list) == [
        ("e1", 2026, 6),
        ("e1", 2026, 7),
    ]


@patch(f"{SERVICE}.record_schedule_import_run")
@patch(f"{SERVICE}.schedule_repository")
@patch(f"{SERVICE}.timesheet_import_repository")
@patch(f"{SERVICE}.get_employee_company_and_statut")
def test_une_heure_negative_est_refusee_avant_toute_ecriture(
    mock_statut, mock_repo, mock_sched, _audit
):
    mock_repo.get_batch.return_value = _lot_de_juillet(
        [
            AiDayEntry(jour=16, heures=-10.5, type="travail", nature="reel"),
            AiDayEntry(jour=17, heures=8.0, type="travail", nature="reel"),
        ]
    )
    mock_statut.return_value = ("c1", "CDI")
    mock_sched.list_schedules_for_employees.return_value = {}

    with pytest.raises(ScheduleAppError) as exc:
        _commit("b-s27")

    assert exc.value.status_code == 422
    assert "BUGNY" in str(exc.value)
    assert "16/07/2026" in str(exc.value)
    assert "-10.5" in str(exc.value) or "−10,5" in str(exc.value)
    mock_sched.bulk_upsert_schedules.assert_not_called()


def test_le_chemin_legacy_refuse_aussi_une_heure_negative():
    payload = PersistTimesheetRequest(
        year=2026,
        month=7,
        employees=[
            PersistTimesheetEmployee(
                employee_id="e1",
                days=[AiDayEntry(jour=16, heures=-0.5, type="travail", nature="reel")],
            )
        ],
    )

    with pytest.raises(ValueError, match="16/07/2026"):
        validate_persist_payload(payload)
