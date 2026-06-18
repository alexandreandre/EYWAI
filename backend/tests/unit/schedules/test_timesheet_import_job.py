"""Tests service jobs async (Supabase mocké)."""

from unittest.mock import MagicMock, patch

import pytest

from app.modules.schedules.application.exceptions import ScheduleAppError


@patch("app.modules.schedules.application.timesheet_import_service._db")
def test_create_import_job_rejects_duplicate(mock_db_fn):
    mock_sb = MagicMock()
    mock_db_fn.return_value = mock_sb
    mock_sb.table.return_value.select.return_value.eq.return_value.in_.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[{"id": "existing"}]
    )
    from app.modules.schedules.application.timesheet_import_service import (
        create_import_job,
    )

    with pytest.raises(ScheduleAppError) as exc:
        create_import_job(
            company_id="c1",
            user_id="u1",
            filename="test.pdf",
            file_content=b"pdf",
            request_json={"year": 2026, "month": 5},
        )
    assert exc.value.status_code == 409


@patch("app.modules.schedules.application.timesheet_import_service.upload_schedule_import_file")
@patch("app.modules.schedules.application.timesheet_import_service._db")
def test_create_import_job_success(mock_db_fn, mock_upload):
    mock_sb = MagicMock()
    mock_db_fn.return_value = mock_sb
    mock_sb.table.return_value.select.return_value.eq.return_value.in_.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[]
    )
    mock_sb.table.return_value.insert.return_value.execute.return_value = MagicMock(
        data=[{"id": "job-1", "status": "queued"}]
    )
    mock_upload.return_value = "c1/job-1/file.pdf"

    from app.modules.schedules.application.timesheet_import_service import (
        create_import_job,
    )

    job = create_import_job(
        company_id="c1",
        user_id="u1",
        filename="test.pdf",
        file_content=b"pdf-content",
        request_json={"year": 2026, "month": 5, "employees": []},
    )
    assert job["id"] == "job-1"
