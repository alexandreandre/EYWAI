from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from app.modules.planning.api.router import (
    _filter_shifts_in_scope,
    _require_shift_scope,
)


def test_planning_filters_shifts_to_allowed_employees():
    user = SimpleNamespace(
        id="user-1",
        is_platform_admin=False,
        has_rh_access_in_company=lambda _cid: False,
    )
    shifts = [
        {"employee_id": "emp-a"},
        {"employee_id": "emp-b"},
    ]
    with patch(
        "app.modules.planning.api.router.access_control_service.filter_allowed_employee_ids",
        return_value=["emp-a"],
    ):
        filtered = _filter_shifts_in_scope(user, "company-1", shifts)

    assert filtered == [{"employee_id": "emp-a"}]


def test_planning_shift_scope_hides_out_of_scope_employee():
    user = SimpleNamespace(id="user-1", is_platform_admin=False)
    with patch(
        "app.modules.planning.api.router.app_queries.get_shift_row",
        return_value={"company_id": "company-1", "employee_id": "emp-x"},
    ), patch(
        "app.modules.planning.api.router.access_control_service.require_employee_access",
        side_effect=HTTPException(status_code=404, detail="Ressource introuvable"),
    ):
        with pytest.raises(HTTPException) as exc:
            _require_shift_scope(user, "company-1", "shift-1", "schedules.view_all")

    assert exc.value.status_code == 404
