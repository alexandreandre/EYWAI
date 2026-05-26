from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from app.modules.badgeuse.application import service
from app.modules.badgeuse.domain.time_tracking import (
    TimeEntry,
    TimeEntryType,
    TimeEntrySource,
)


@pytest.fixture(autouse=True)
def _badge_settings(monkeypatch):
    monkeypatch.setenv("BADGEUSE_QR_SECRET", "test-secret")
    monkeypatch.setattr(
        service,
        "get_badgeuse_settings",
        lambda _cid: {"allow_self_toggle": True, "scan_mode_enabled": True},
    )


def test_list_punch_candidates_filters_search_and_not_badged():
    employees = [
        {
            "id": "e1",
            "first_name": "Jean",
            "last_name": "Dupont",
            "username": "jean.dupont",
            "statut": "CDI",
        },
        {
            "id": "e2",
            "first_name": "Marie",
            "last_name": "Martin",
            "username": "marie.martin",
            "statut": "CDI",
        },
    ]
    entry = TimeEntry(
        id="ev-1",
        employee_id="e1",
        company_id="comp-1",
        timestamp=datetime(2026, 5, 25, 8, 0, 0),
        event_type=TimeEntryType.ENTREE,
        source=TimeEntrySource.QR_SCAN,
    )

    mock_supabase = MagicMock()
    mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.order.return_value.execute.return_value = MagicMock(
        data=employees
    )

    with (
        patch("app.core.database.supabase", mock_supabase),
        patch.object(
            service.time_entry_repository,
            "get_entries_for_company_between",
            return_value=[
                {
                    "id": "ev-1",
                    "employee_id": "e1",
                    "company_id": "comp-1",
                    "timestamp": entry.timestamp.isoformat(),
                    "event_type": "ENTREE",
                    "source": "QR_SCAN",
                }
            ],
        ),
        patch.object(service.time_entry_repository, "_row_to_entry", return_value=entry),
        patch.object(service, "_employee_is_forfait_jour", return_value=False),
    ):
        not_badged = service.list_punch_candidates(
            company_id="comp-1", only_not_badged_today=True
        )
        assert len(not_badged) == 1
        assert not_badged[0]["employee_id"] == "e2"

        found = service.list_punch_candidates(
            company_id="comp-1", search="marie", limit=10
        )
        assert len(found) == 1
        assert found[0]["display_name"] == "Marie Martin"
        assert found[0]["next_action"] == "ENTREE"
