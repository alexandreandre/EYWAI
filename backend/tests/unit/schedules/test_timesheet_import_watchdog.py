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
        patch.object(svc, "_db", return_value=_db_returning(_job_row("extracting", 11))),
        patch.object(svc, "_update_job") as mock_update,
    ):
        job = svc.get_import_job("job-1")

    assert job["status"] == "failed"
    assert "interrompue" in job["error_message"]
    payload = mock_update.call_args.args[1]
    assert payload["status"] == "failed"
    assert payload["progress_json"]["phase"] == "failed"


def test_get_import_job_returns_failed_copy_when_update_raises():
    """Un GET ne doit jamais lever 500 si l'écriture de marquage watchdog échoue."""
    from app.modules.schedules.application import timesheet_import_service as svc

    with (
        patch.object(svc, "_db", return_value=_db_returning(_job_row("extracting", 11))),
        patch.object(svc, "_update_job", side_effect=RuntimeError("db down")),
    ):
        job = svc.get_import_job("job-1")

    assert job["status"] == "failed"
    assert "interrompue" in job["error_message"]


def test_raise_if_job_cancelled_raises_on_failed_status():
    """Un job déjà marqué failed par le watchdog doit couper le thread zombie."""
    from app.modules.schedules.application import timesheet_import_service as svc
    from app.modules.schedules.application.exceptions import ScheduleAppError

    with patch.object(svc, "_db", return_value=_db_returning(_job_row("failed", 1))):
        with pytest.raises(ScheduleAppError) as exc_info:
            svc._raise_if_job_cancelled("job-1")

    assert exc_info.value.code == "cancelled"
    assert exc_info.value.message == "Import interrompu."


def test_raise_if_job_cancelled_still_raises_on_cancelled_status():
    from app.modules.schedules.application import timesheet_import_service as svc
    from app.modules.schedules.application.exceptions import ScheduleAppError

    with patch.object(svc, "_db", return_value=_db_returning(_job_row("cancelled", 1))):
        with pytest.raises(ScheduleAppError) as exc_info:
            svc._raise_if_job_cancelled("job-1")

    assert exc_info.value.code == "cancelled"


def test_job_is_terminal_true_for_failed_and_cancelled():
    from app.modules.schedules.application import timesheet_import_service as svc

    with patch.object(svc, "_db", return_value=_db_returning({"status": "failed"})):
        assert svc._job_is_terminal("job-1") is True

    with patch.object(svc, "_db", return_value=_db_returning({"status": "cancelled"})):
        assert svc._job_is_terminal("job-1") is True


def test_job_is_terminal_false_for_active_status():
    from app.modules.schedules.application import timesheet_import_service as svc

    with patch.object(svc, "_db", return_value=_db_returning({"status": "extracting"})):
        assert svc._job_is_terminal("job-1") is False


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


def test_stale_queued_job_marked_failed():
    """Un job resté queued (jamais promu à extracting, instance morte avant
    l'upload/la promotion) doit lui aussi être fermé par le watchdog."""
    from app.modules.schedules.application import timesheet_import_service as svc

    with (
        patch.object(svc, "_db", return_value=_db_returning(_job_row("queued", 11))),
        patch.object(svc, "_update_job") as mock_update,
    ):
        job = svc.get_import_job("job-1")

    assert job["status"] == "failed"
    assert "interrompue" in job["error_message"]
    payload = mock_update.call_args.args[1]
    assert payload["status"] == "failed"


def test_fresh_queued_job_untouched():
    from app.modules.schedules.application import timesheet_import_service as svc

    with (
        patch.object(svc, "_db", return_value=_db_returning(_job_row("queued", 1))),
        patch.object(svc, "_update_job") as mock_update,
    ):
        job = svc.get_import_job("job-1")

    assert job["status"] == "queued"
    mock_update.assert_not_called()
