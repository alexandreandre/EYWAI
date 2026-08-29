"""Tests service jobs async (Supabase mocké)."""

from unittest.mock import MagicMock, patch

import pytest

from app.modules.schedules.application.exceptions import ScheduleAppError


@patch("app.modules.schedules.application.timesheet_import_service._db")
def test_create_import_job_cancels_active(mock_db_fn):
    mock_sb = MagicMock()
    mock_db_fn.return_value = mock_sb
    select_chain = mock_sb.table.return_value.select.return_value
    select_chain.eq.return_value.in_.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[{"id": "existing"}]
    )
    select_chain.eq.return_value.in_.return_value.execute.return_value = MagicMock(
        data=[{"id": "existing"}]
    )
    select_chain.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
        data={"id": "existing", "status": "extracting"}
    )
    mock_sb.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[{"id": "existing", "status": "cancelled"}]
    )
    mock_sb.table.return_value.insert.return_value.execute.return_value = MagicMock(
        data=[{"id": "job-2", "status": "queued"}]
    )

    with patch(
        "app.modules.schedules.application.timesheet_import_service.upload_schedule_import_file",
        return_value="c1/job-2/file.pdf",
    ):
        from app.modules.schedules.application.timesheet_import_service import (
            create_import_job,
        )

        job = create_import_job(
            company_id="c1",
            user_id="u1",
            filename="test.pdf",
            file_content=b"pdf",
            request_json={"year": 2026, "month": 5},
        )
    assert job["id"] == "job-2"


@patch("app.modules.schedules.application.timesheet_import_service.upload_schedule_import_file")
@patch("app.modules.schedules.application.timesheet_import_service._db")
def test_create_import_job_success(mock_db_fn, mock_upload):
    mock_sb = MagicMock()
    mock_db_fn.return_value = mock_sb
    select_chain = mock_sb.table.return_value.select.return_value
    select_chain.eq.return_value.in_.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[]
    )
    select_chain.eq.return_value.in_.return_value.execute.return_value = MagicMock(data=[])
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


def test_create_import_job_promotes_to_extracting_even_if_storage_fails():
    """Un échec d'upload PDF ne doit pas laisser le job en queued à vie.

    Avant correctif, le passage à status="extracting" était fait DANS le try
    du stockage : si l'upload levait, l'except avalait tout et le job restait
    queued pour toujours — hors de portée du watchdog qui ne surveille que
    extracting (avant l'extension queued du même correctif).
    """
    from app.modules.schedules.application import timesheet_import_service as svc

    mock_sb = MagicMock()
    select_chain = mock_sb.table.return_value.select.return_value
    select_chain.eq.return_value.in_.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[]
    )
    select_chain.eq.return_value.in_.return_value.execute.return_value = MagicMock(data=[])
    mock_sb.table.return_value.insert.return_value.execute.return_value = MagicMock(
        data=[{"id": "job-1", "status": "queued"}]
    )

    with (
        patch.object(svc, "_db", return_value=mock_sb),
        patch.object(
            svc,
            "upload_schedule_import_file",
            side_effect=RuntimeError("stockage indisponible"),
        ),
        patch.object(svc, "_update_job") as mock_update,
    ):
        job = svc.create_import_job(
            company_id="c1",
            user_id="u1",
            filename="test.pdf",
            file_content=b"pdf-content",
            request_json={"year": 2026, "month": 5, "employees": []},
            cancel_active=False,
        )

    assert job["file_storage_path"] is None
    mock_update.assert_called_once()
    payload = mock_update.call_args.args[1]
    assert payload["status"] == "extracting"
    assert "file_storage_path" not in payload


@patch("app.modules.schedules.application.timesheet_import_service.get_import_job")
def test_raise_if_job_cancelled(mock_get):
    from app.modules.schedules.application.timesheet_import_service import (
        _raise_if_job_cancelled,
    )

    mock_get.return_value = {"id": "j1", "status": "cancelled"}
    with pytest.raises(ScheduleAppError) as exc:
        _raise_if_job_cancelled("j1")
    assert exc.value.code == "cancelled"
