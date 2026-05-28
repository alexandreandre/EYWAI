"""Résolution employé sur les routes /api/absences/employees/me/*."""

from unittest.mock import patch

import pytest
from fastapi import HTTPException

from app.modules.absences.api.router import (
    _resolve_create_absence_employee_id,
    _resolve_employee_id_for_current_user,
)
from app.modules.users.schemas.responses import CompanyAccess, User

TEST_COMPANY_ID = "co-abs"


def _collab_user(**kwargs) -> User:
    defaults = {
        "id": "auth-uid",
        "email": "c@test.com",
        "accessible_companies": [
            CompanyAccess(
                company_id=TEST_COMPANY_ID,
                company_name="Co",
                role="collaborateur",
                is_primary=True,
            )
        ],
        "active_company_id": TEST_COMPANY_ID,
    }
    defaults.update(kwargs)
    return User(**defaults)


def _rh_user() -> User:
    return _collab_user(id="rh-uid", email="rh@test.com").model_copy(
        update={
            "accessible_companies": [
                CompanyAccess(
                    company_id=TEST_COMPANY_ID,
                    company_name="Co",
                    role="rh",
                    is_primary=True,
                )
            ]
        }
    )


@patch(
    "app.modules.absences.api.router.absence_router.resolve_employee_id_for_user",
    return_value="emp-resolved",
)
def test_resolve_employee_id_for_current_user(_mock):
    assert _resolve_employee_id_for_current_user(_collab_user()) == "emp-resolved"


@patch(
    "app.modules.absences.api.router.absence_router.resolve_employee_id_for_user",
    return_value=None,
)
def test_resolve_employee_id_for_current_user_raises_404(_mock):
    with pytest.raises(HTTPException) as exc:
        _resolve_employee_id_for_current_user(_collab_user())
    assert exc.value.status_code == 404


@patch(
    "app.modules.absences.api.router.absence_router.resolve_employee_id_for_user",
    return_value="emp-resolved",
)
def test_create_absence_maps_auth_uid_to_employee(_mock):
    resolved = _resolve_create_absence_employee_id(_collab_user(), "auth-uid")
    assert resolved == "emp-resolved"


@patch(
    "app.modules.absences.api.router.absence_router.resolve_employee_id_for_user",
    return_value="emp-resolved",
)
def test_create_absence_denies_other_employee_for_collab(_mock):
    with pytest.raises(HTTPException) as exc:
        _resolve_create_absence_employee_id(_collab_user(), "other-emp")
    assert exc.value.status_code == 403


@patch(
    "app.modules.absences.api.router.absence_router.get_employee_company_id",
    return_value=TEST_COMPANY_ID,
)
def test_create_absence_allows_rh_for_company_employee(_mock_company):
    resolved = _resolve_create_absence_employee_id(_rh_user(), "emp-target")
    assert resolved == "emp-target"
