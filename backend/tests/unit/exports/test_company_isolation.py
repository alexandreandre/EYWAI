from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from app.modules.exports.api.router import _require_exports_company_access


def test_exports_rejects_mismatched_active_company():
    user = SimpleNamespace(
        id="user-1",
        is_platform_admin=False,
        active_company_id="company-1",
        has_rh_access_in_company=lambda cid: cid == "company-2",
    )
    with pytest.raises(HTTPException) as exc:
        _require_exports_company_access(user, "company-2")

    assert exc.value.status_code == 404


def test_exports_allows_matching_active_company():
    user = SimpleNamespace(
        id="user-1",
        is_platform_admin=False,
        active_company_id="company-1",
        has_rh_access_in_company=lambda cid: cid == "company-1",
    )
    _require_exports_company_access(user, "company-1")
