"""Tests commit batch import pointages (mock DB)."""

from unittest.mock import patch

import pytest

from app.modules.schedules.application.exceptions import ScheduleAppError
from app.modules.schedules.schemas.ai import (
    AiCalendarProposalResponse,
    AiDayEntry,
    AiEmployeeProposal,
)
from app.modules.schedules.schemas.timesheet_import import TimesheetImportCommitRequest


@patch("app.modules.schedules.application.timesheet_import.commit_service.schedule_repository")
@patch("app.modules.schedules.application.timesheet_import.commit_service.timesheet_import_repository")
@patch(
    "app.modules.schedules.application.timesheet_import.commit_service.get_employee_company_and_statut"
)
def test_commit_batch_bulk(mock_statut, mock_repo, mock_sched_repo):
    mock_repo.get_batch.return_value = {
        "id": "b1",
        "company_id": "c1",
        "status": "previewed",
        "file_hash": "abc123",
        "preview_json": AiCalendarProposalResponse(
            year=2026,
            month=5,
            source="test",
            employees=[
                AiEmployeeProposal(
                    raw_name="ADAM",
                    employee_id="e1",
                    days=[
                        AiDayEntry(jour=1, heures=8.0, type="travail", nature="reel"),
                    ],
                    review_status="ok",
                    match_confidence="high",
                )
            ],
        ).model_dump(mode="json"),
        "summary_json": {},
    }
    mock_statut.return_value = ("c1", "CDI")
    mock_sched_repo.list_schedules_for_employees.return_value = {}

    from app.modules.schedules.application.timesheet_import.commit_service import (
        commit_batch_bulk,
    )

    result = commit_batch_bulk(
        "b1",
        company_id="c1",
        request=TimesheetImportCommitRequest(),
    )
    assert result["status"] == "committed"
    assert result["total_days_written"] == 1
    mock_sched_repo.bulk_upsert_schedules.assert_called_once()
    mock_repo.release_committed_file_hash_lock.assert_called_once_with(
        "c1",
        "abc123",
        keep_batch_id="b1",
    )


@patch("app.modules.schedules.application.timesheet_import.commit_service.schedule_repository")
@patch("app.modules.schedules.application.timesheet_import.commit_service.timesheet_import_repository")
@patch(
    "app.modules.schedules.application.timesheet_import.commit_service.get_employee_company_and_statut"
)
def test_commit_batch_bulk_releases_existing_hash_lock(mock_statut, mock_repo, mock_sched_repo):
    mock_repo.get_batch.return_value = {
        "id": "b2",
        "company_id": "c1",
        "status": "previewed",
        "file_hash": "same-hash",
        "filename": "calendrier.xlsx",
        "preview_json": AiCalendarProposalResponse(
            year=2026,
            month=5,
            source="test",
            employees=[
                AiEmployeeProposal(
                    raw_name="ADAM",
                    employee_id="e1",
                    days=[AiDayEntry(jour=1, heures=8.0, type="travail", nature="prevu")],
                    review_status="ok",
                    match_confidence="high",
                )
            ],
        ).model_dump(mode="json"),
        "summary_json": {},
    }
    mock_statut.return_value = ("c1", "CDI")
    mock_sched_repo.list_schedules_for_employees.return_value = {}

    from app.modules.schedules.application.timesheet_import.commit_service import (
        commit_batch_bulk,
    )

    result = commit_batch_bulk(
        "b2",
        company_id="c1",
        request=TimesheetImportCommitRequest(),
    )

    assert result["status"] == "committed"
    mock_repo.release_committed_file_hash_lock.assert_called_once_with(
        "c1",
        "same-hash",
        keep_batch_id="b2",
    )


@patch("app.modules.schedules.application.timesheet_import.commit_service.timesheet_import_repository")
def test_begin_commit_releases_existing_hash_lock(mock_repo):
    mock_repo.get_batch.return_value = {
        "id": "b-new",
        "status": "previewed",
        "file_hash": "dup-hash",
        "summary_json": {},
    }
    from app.modules.schedules.application.timesheet_import.commit_service import (
        begin_commit_batch,
    )

    started = begin_commit_batch(
        "b-new",
        company_id="c1",
        request=TimesheetImportCommitRequest(),
    )

    assert started is True
    mock_repo.release_committed_file_hash_lock.assert_called_once_with(
        "c1",
        "dup-hash",
        keep_batch_id="b-new",
    )


@patch("app.modules.schedules.application.timesheet_import.commit_service.timesheet_import_repository")
def test_begin_commit_rejects_committed(mock_repo):
    mock_repo.get_batch.return_value = {"id": "b1", "status": "committed", "summary_json": {}}
    from app.modules.schedules.application.timesheet_import.commit_service import (
        begin_commit_batch,
    )

    with pytest.raises(ScheduleAppError) as exc:
        begin_commit_batch(
            "b1",
            company_id="c1",
            request=TimesheetImportCommitRequest(),
        )
    assert exc.value.status_code == 409


def _arret_valide(jour: int) -> dict:
    return {
        "jour": jour,
        "type": "arret_maladie",
        "heures_prevues": 0,
        "origine": "absence",
        "arret_type": "maladie_simple",
        "subrogation_active": True,
    }


@patch("app.modules.schedules.application.timesheet_import.commit_service.record_schedule_import_run")
@patch("app.modules.schedules.application.timesheet_import.commit_service.schedule_repository")
@patch("app.modules.schedules.application.timesheet_import.commit_service.timesheet_import_repository")
@patch(
    "app.modules.schedules.application.timesheet_import.commit_service.get_employee_company_and_statut"
)
def test_commit_bulk_ne_detruit_pas_une_absence_validee(
    mock_statut, mock_repo, mock_sched_repo, _mock_audit
):
    """Le commit d'import écrivait le planning sans passer par la fusion serveur."""
    mock_repo.get_batch.return_value = {
        "id": "b-abs",
        "company_id": "c1",
        "status": "previewed",
        "preview_json": AiCalendarProposalResponse(
            year=2026,
            month=7,
            source="test",
            employees=[
                AiEmployeeProposal(
                    raw_name="ADAM",
                    employee_id="e1",
                    days=[
                        AiDayEntry(jour=3, heures=7.0, type="travail", nature="prevu"),
                        AiDayEntry(jour=4, heures=8.5, type="travail", nature="prevu"),
                    ],
                    review_status="ok",
                    match_confidence="high",
                )
            ],
        ).model_dump(mode="json"),
        "summary_json": {},
    }
    mock_statut.return_value = ("c1", "CDI")
    mock_sched_repo.list_schedules_for_employees.return_value = {
        "e1": {
            "employee_id": "e1",
            "company_id": "c1",
            "planned_calendar": {
                "calendrier_prevu": [
                    _arret_valide(3),
                    {"jour": 4, "type": "travail", "heures_prevues": 7.0},
                ]
            },
            "actual_hours": {},
        }
    }

    from app.modules.schedules.application.timesheet_import.commit_service import (
        commit_batch_bulk,
    )

    result = commit_batch_bulk(
        "b-abs",
        company_id="c1",
        request=TimesheetImportCommitRequest(),
    )

    payloads = mock_sched_repo.bulk_upsert_schedules.call_args[0][0]
    jours = {
        d["jour"]: d for d in payloads[0]["planned_calendar"]["calendrier_prevu"]
    }
    assert jours[3]["type"] == "arret_maladie"
    assert jours[3]["arret_type"] == "maladie_simple"
    assert jours[4]["heures_prevues"] == 8.5
    assert [w["jour"] for w in result["warnings"]] == [3]
