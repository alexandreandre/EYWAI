from datetime import datetime
from unittest.mock import patch

import pytest

from app.modules.badgeuse.application import service
from app.modules.badgeuse.application.badge_tokens import build_qr_payload
from app.modules.badgeuse.domain.time_tracking import (
    TimeEntry,
    TimeEntryType,
    TimeEntrySource,
)


def _entry(ts: str, kind: TimeEntryType) -> TimeEntry:
    return TimeEntry(
        id="ev-1",
        employee_id="emp-1",
        company_id="comp-1",
        timestamp=datetime.fromisoformat(ts),
        event_type=kind,
        source=TimeEntrySource.EMPLOYE,
    )


@pytest.fixture(autouse=True)
def _badge_settings(monkeypatch):
    monkeypatch.setenv("BADGEUSE_QR_SECRET", "test-secret")
    monkeypatch.setattr(
        service,
        "get_badgeuse_settings",
        lambda _cid: {"allow_self_toggle": True, "scan_mode_enabled": True},
    )


class TestPunchFromQr:
    def test_punch_entree_when_no_entries(self):
        creds = {
            "token_version": 1,
            "secret_salt": "salt-1",
            "revoked_at": None,
        }
        payload = build_qr_payload(
            company_id="comp-1",
            employee_id="emp-1",
            token_version=1,
            secret_salt="salt-1",
        )
        employee_row = {
            "id": "emp-1",
            "first_name": "Marie",
            "last_name": "Dupont",
            "statut": "ouvrier",
        }

        with (
            patch.object(
                service.badge_credentials_repository,
                "get_credentials",
                return_value=creds,
            ),
            patch.object(
                service._employee_repository,
                "get_by_id",
                return_value=employee_row,
            ),
            patch.object(
                service.time_entry_repository,
                "get_entries_for_employee_on_day",
                return_value=[],
            ),
            patch.object(
                service.time_entry_repository,
                "insert_entry",
            ) as insert_mock,
            patch.object(
                service.time_entry_repository,
                "get_entries_for_employee_on_day",
                side_effect=[
                    [],
                    [_entry("2026-05-25T08:00:00", TimeEntryType.ENTREE)],
                ],
            ),
        ):
            result = service.punch_from_qr(
                qr_payload=payload,
                employee_id=None,
                company_id="comp-1",
                actor_user_id="rh-1",
            )

        assert result["event_type"] == "ENTREE"
        assert result["employee_name"] == "Marie Dupont"
        insert_mock.assert_called_once()
        call_kw = insert_mock.call_args.kwargs
        assert call_kw["source"] == TimeEntrySource.QR_SCAN

    def test_debounce_raises(self):
        recent = _entry("2026-05-25T08:00:00", TimeEntryType.ENTREE)
        with pytest.raises(ValueError, match="trop rapide"):
            service._check_debounce([recent], datetime.fromisoformat("2026-05-25T08:00:02"))

    def test_forfait_jour_rejected(self):
        with patch.object(
            service._employee_repository,
            "get_by_id",
            return_value={
                "id": "emp-1",
                "statut": "cadre forfait jour",
                "first_name": "X",
                "last_name": "Y",
            },
        ):
            with pytest.raises(PermissionError):
                service.punch_from_qr(
                    qr_payload=None,
                    employee_id="emp-1",
                    company_id="comp-1",
                    actor_user_id="rh-1",
                )
