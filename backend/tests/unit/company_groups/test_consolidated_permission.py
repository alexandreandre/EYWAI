from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from app.modules.company_groups.api.router import _require_consolidated_view_permission


def test_consolidated_stats_requires_group_permission():
    user = SimpleNamespace(
        id="user-1", is_platform_admin=False, active_company_id="company-1"
    )
    with patch(
        "app.modules.company_groups.api.router.access_control_service.check_user_has_permission",
        return_value=False,
    ):
        with pytest.raises(HTTPException) as exc:
            _require_consolidated_view_permission(user)

    assert exc.value.status_code == 403
    assert "consultation consolidée" in str(exc.value.detail)
