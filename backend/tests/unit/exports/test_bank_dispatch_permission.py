from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from app.modules.exports.api.router import _require_bank_dispatch_permission


def test_bank_dispatch_requires_explicit_permission():
    user = SimpleNamespace(id="user-1", is_platform_admin=False)
    with patch(
        "app.modules.exports.api.router.access_control_service.check_user_has_permission",
        return_value=False,
    ):
        with pytest.raises(HTTPException) as exc:
            _require_bank_dispatch_permission(user, "company-1")

    assert exc.value.status_code == 403
    assert "envoi bancaire" in str(exc.value.detail)
