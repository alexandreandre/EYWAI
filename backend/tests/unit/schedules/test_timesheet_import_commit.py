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
