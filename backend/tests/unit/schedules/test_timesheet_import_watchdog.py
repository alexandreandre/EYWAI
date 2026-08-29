"""Un job « extracting » sans heartbeat depuis > 5 min est marqué failed."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


def _job_row(status: str, updated_minutes_ago: float) -> dict:
    return {
        "id": "job-1",
        "status": status,
        "updated_at": (
            datetime.now(timezone.utc) - timedelta(minutes=updated_minutes_ago)
        ).isoformat(),
    }


def _db_returning(row: dict) -> MagicMock:
    db = MagicMock()
    db.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = row
    return db


def test_stale_extracting_job_marked_failed():
    from app.modules.schedules.application import timesheet_import_service as svc

    with (
        patch.object(svc, "_db", return_value=_db_returning(_job_row("extracting", 6))),
        patch.object(svc, "_update_job") as mock_update,
    ):
        job = svc.get_import_job("job-1")

    assert job["status"] == "failed"
    assert "interrompue" in job["error_message"]
    payload = mock_update.call_args.args[1]
    assert payload["status"] == "failed"


def test_fresh_extracting_job_untouched():
    from app.modules.schedules.application import timesheet_import_service as svc

    with (
        patch.object(svc, "_db", return_value=_db_returning(_job_row("extracting", 1))),
        patch.object(svc, "_update_job") as mock_update,
    ):
        job = svc.get_import_job("job-1")

    assert job["status"] == "extracting"
    mock_update.assert_not_called()


def test_completed_job_untouched():
    from app.modules.schedules.application import timesheet_import_service as svc

    with (
        patch.object(svc, "_db", return_value=_db_returning(_job_row("completed", 60))),
        patch.object(svc, "_update_job") as mock_update,
    ):
        job = svc.get_import_job("job-1")

    assert job["status"] == "completed"
    mock_update.assert_not_called()
