from types import SimpleNamespace
from unittest.mock import patch

from app.modules.training.api.router import _filter_enrollments_in_scope
from app.modules.training.schemas.responses import TrainingEnrollment


def test_training_filters_enrollments_by_scope():
    user = SimpleNamespace(
        id="user-1",
        is_platform_admin=False,
        has_rh_access_in_company=lambda _cid: False,
    )
    rows = [
        TrainingEnrollment(
            id="e1",
            company_id="company-1",
            training_id="t1",
            employee_id="emp-a",
            status="planned",
        ),
        TrainingEnrollment(
            id="e2",
            company_id="company-1",
            training_id="t1",
            employee_id="emp-b",
            status="planned",
        ),
    ]
    with patch(
        "app.modules.training.api.router.access_control_service.filter_allowed_employee_ids",
        return_value=["emp-b"],
    ):
        filtered = _filter_enrollments_in_scope(user, "company-1", rows)

    assert [row.employee_id for row in filtered] == ["emp-b"]
