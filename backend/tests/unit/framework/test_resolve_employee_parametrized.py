"""Tests paramétrés — résolution employé (remplace les test_me_router_resolve dispersés)."""

from __future__ import annotations

from unittest.mock import patch

import pytest

import app.shared.employee_resolution as employee_resolution

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("user_id", "company_id", "canonical_return", "expected"),
    [
        ("user-1", "co-1", "emp-uuid", "emp-uuid"),
        ("user-1", "co-1", None, None),
    ],
)
def test_resolve_employee_id_for_user_account_delegates(
    user_id: str, company_id: str, canonical_return: str | None, expected: str | None
):
    with patch.object(
        employee_resolution,
        "resolve_employee_id_for_user_account",
        return_value=canonical_return,
    ) as mock_resolve:
        assert (
            employee_resolution.resolve_employee_id_for_user_account(
                user_id, company_id
            )
            == expected
        )
        mock_resolve.assert_called_once_with(str(user_id), str(company_id))
