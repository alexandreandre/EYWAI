"""Résolution employé pour les endpoints /api/me/badgeuse."""

from datetime import date, timedelta
from unittest.mock import MagicMock, patch

from app.modules.badgeuse.application import service as badgeuse_service
from app.modules.users.schemas.responses import User


def _user(**kwargs) -> User:
    defaults = {
        "id": "auth-uid",
        "email": "collab@example.com",
        "active_company_id": "co-1",
        "accessible_companies": [],
    }
    defaults.update(kwargs)
    return User(**defaults)


@patch(
    "app.modules.badgeuse.application.service.resolve_my_employee_id_for_user",
    return_value="emp-resolved",
)
@patch("app.modules.badgeuse.application.service.time_entry_repository")
@patch("app.modules.badgeuse.application.service._employee_repository")
@patch("app.modules.badgeuse.application.service.get_badgeuse_settings")
@patch("app.modules.badgeuse.application.service.compute_day_summary")
def test_get_today_status_uses_resolved_employee_id(
    mock_summary,
    mock_settings,
    mock_emp_repo,
    mock_entries,
    _mock_resolve,
):
    mock_settings.return_value = {"allow_self_toggle": True}
    mock_entries.get_entries_for_employee_on_day.return_value = []
    mock_emp_repo.get_by_id.return_value = {
        "first_name": "Ada",
        "last_name": "Lovelace",
        "username": "ada",
    }
    mock_summary.return_value = MagicMock(
        date=date(2026, 5, 26),
        total_duration=timedelta(0),
        sequences=[],
        anomalies=[],
    )

    badgeuse_service.get_today_status_for_me(_user(), day=date(2026, 5, 26))

    mock_entries.get_entries_for_employee_on_day.assert_called_once()
    call_kw = mock_entries.get_entries_for_employee_on_day.call_args.kwargs
    assert call_kw["employee_id"] == "emp-resolved"


@patch(
    "app.modules.badgeuse.application.service.resolve_my_employee_id_for_user",
    return_value=None,
)
def test_get_today_status_ineligible_when_no_employee_link(_mock_resolve):
    result = badgeuse_service.get_today_status_for_me(_user())

    assert result["is_eligible_for_badgeuse"] is False
    assert "fiche employé" in (result.get("reason") or "").lower()


@patch("app.modules.badgeuse.application.service._user_is_forfait_jour", return_value=False)
@patch("app.modules.badgeuse.application.service.get_badgeuse_settings")
@patch(
    "app.modules.badgeuse.application.service.resolve_my_employee_id_for_user",
    return_value="emp-resolved",
)
@patch("app.modules.badgeuse.application.service._insert_toggle_entry")
@patch("app.modules.badgeuse.application.service.time_entry_repository")
@patch("app.modules.badgeuse.application.service.get_today_status_for_me")
def test_toggle_badge_uses_resolved_employee_id(
    mock_status,
    mock_entries,
    mock_insert,
    _mock_resolve,
    mock_settings,
    _mock_forfait,
):
    mock_settings.return_value = {"allow_self_toggle": True}
    mock_entries.get_entries_for_employee_on_day.return_value = []
    mock_status.return_value = {"ok": True}

    badgeuse_service.toggle_badge_for_me(_user())

    mock_insert.assert_called_once()
    assert mock_insert.call_args.kwargs["employee_id"] == "emp-resolved"
    assert mock_insert.call_args.kwargs["created_by"] == "auth-uid"


@patch("app.modules.badgeuse.application.service._user_is_forfait_jour", return_value=False)
@patch("app.modules.badgeuse.application.service.get_badgeuse_settings")
@patch(
    "app.modules.badgeuse.application.service.resolve_my_employee_id_for_user",
    return_value=None,
)
def test_toggle_badge_denied_when_no_employee_link(
    _mock_resolve, mock_settings, _mock_forfait
):
    import pytest

    mock_settings.return_value = {"allow_self_toggle": True}
    with pytest.raises(PermissionError, match="fiche employé"):
        badgeuse_service.toggle_badge_for_me(_user())
