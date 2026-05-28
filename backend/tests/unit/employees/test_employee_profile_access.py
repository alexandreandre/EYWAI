"""Contrôle d'accès GET /api/employees/{id} pour les collaborateurs."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.modules.employees.api.deps import assert_can_read_employee_profile


def _user(*, user_id: str = "user-1", rh: bool = False, platform: bool = False):
    u = MagicMock(
        spec=["id", "has_access_to_company", "has_rh_access_in_company"]
    )
    u.id = user_id
    u.has_access_to_company.return_value = True
    u.has_rh_access_in_company.return_value = rh
    return u


@patch("app.modules.employees.api.deps.is_platform_admin", return_value=False)
def test_collaborateur_can_read_own_profile_by_user_id(_mock_platform):
    user = _user(user_id="user-1")
    with patch(
        "app.modules.employees.api.deps.resolve_employee_id_for_user_account",
        return_value=None,
    ):
        assert_can_read_employee_profile(user, "user-1", "co-1")


@patch("app.modules.employees.api.deps.is_platform_admin", return_value=False)
def test_collaborateur_can_read_resolved_employee_id(_mock_platform):
    user = _user(user_id="auth-1")
    with patch(
        "app.modules.employees.api.deps.resolve_employee_id_for_user_account",
        return_value="emp-99",
    ):
        assert_can_read_employee_profile(user, "emp-99", "co-1")


@patch("app.modules.employees.api.deps.is_platform_admin", return_value=False)
def test_collaborateur_cannot_read_other_employee(_mock_platform):
    user = _user(user_id="auth-1")
    with patch(
        "app.modules.employees.api.deps.resolve_employee_id_for_user_account",
        return_value="emp-99",
    ):
        with pytest.raises(HTTPException) as exc:
            assert_can_read_employee_profile(user, "emp-other", "co-1")
        assert exc.value.status_code == 403


@patch("app.modules.employees.api.deps.is_platform_admin", return_value=False)
def test_rh_can_read_any_employee_in_company(_mock_platform):
    user = _user(rh=True)
    with patch(
        "app.modules.employees.api.deps.resolve_employee_id_for_user_account",
    ) as mock_resolve:
        assert_can_read_employee_profile(user, "any-emp", "co-1")
        mock_resolve.assert_not_called()
