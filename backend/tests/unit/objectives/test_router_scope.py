from types import SimpleNamespace
from unittest.mock import patch

from app.modules.objectives.api.router import _filter_objectives_in_scope
from app.modules.objectives.schemas.responses import EmployeeObjective


def test_objectives_filters_rows_to_allowed_employees():
    user = SimpleNamespace(
        id="user-1",
        is_platform_admin=False,
        has_rh_access_in_company=lambda _cid: False,
    )
    rows = [
        EmployeeObjective(
            id="o1",
            company_id="company-1",
            employee_id="emp-a",
            title="A",
            type="qualitative",
            period_year=2026,
            status="active",
        ),
        EmployeeObjective(
            id="o2",
            company_id="company-1",
            employee_id="emp-b",
            title="B",
            type="qualitative",
            period_year=2026,
            status="active",
        ),
    ]
    with patch(
        "app.modules.objectives.api.router.access_control_service.filter_allowed_employee_ids",
        return_value=["emp-a"],
    ):
        filtered = _filter_objectives_in_scope(user, "company-1", rows)

    assert [row.employee_id for row in filtered] == ["emp-a"]
