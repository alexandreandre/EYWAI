from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from app.modules.payslips.api.router import _require_payslip_scope


def test_payslip_scope_hides_cross_company_payslip():
    user = SimpleNamespace(active_company_id="company-1")
    with patch(
        "app.modules.payslips.api.router.get_payslip_meta_for_access",
        return_value={"company_id": "company-2", "employee_id": "employee-2"},
    ):
        with pytest.raises(HTTPException) as exc:
            _require_payslip_scope(user, "payslip-1", "payslips.validate")

    assert exc.value.status_code == 404
