from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from app.modules.saisies_avances.api.router import (
    _filter_company_rows_in_scope,
    _require_advance_scope,
)


def test_advances_filter_keeps_only_active_company_rows():
    user = SimpleNamespace(
        id="user-1",
        is_platform_admin=False,
        has_rh_access_in_company=lambda _cid: False,
    )
    rows = [
        {"company_id": "company-1", "employee_id": "emp-a"},
        {"company_id": "company-2", "employee_id": "emp-b"},
    ]
    with patch(
        "app.modules.saisies_avances.api.router.access_control_service.filter_allowed_employee_ids",
        return_value=["emp-a"],
    ):
        filtered = _filter_company_rows_in_scope(
            user, "company-1", "advances.view_all", rows
        )

    assert filtered == [{"company_id": "company-1", "employee_id": "emp-a"}]


def test_advance_scope_hides_cross_company_record():
    user = SimpleNamespace(id="user-1", is_platform_admin=False)
    with patch(
        "app.modules.saisies_avances.api.router.queries.get_salary_advance",
        return_value={"company_id": "company-2", "employee_id": "emp-1"},
    ):
        with pytest.raises(HTTPException) as exc:
            _require_advance_scope(user, "company-1", "adv-1", "advances.view_all")

    assert exc.value.status_code == 404
