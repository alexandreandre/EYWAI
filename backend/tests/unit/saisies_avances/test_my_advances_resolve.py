"""Résolution employé pour les routes avances collaborateur (/employees/me/*)."""

from unittest.mock import patch

import pytest

from app.modules.saisies_avances.application.dto import NotFoundError
from app.modules.saisies_avances.application.queries import (
    get_my_advance_available_for_user_account,
    get_my_salary_advances_for_user_account,
    resolve_employee_id_for_advance_account,
)


@patch(
    "app.modules.employees.infrastructure.queries.resolve_employee_id_for_user_account",
    return_value="emp-resolved",
)
def test_resolve_employee_id_for_advance_account_uses_company(mock_resolve):
    assert resolve_employee_id_for_advance_account("auth-1", "co-1") == "emp-resolved"
    mock_resolve.assert_called_once_with("auth-1", "co-1")


def test_resolve_employee_id_for_advance_account_none_without_company():
    assert resolve_employee_id_for_advance_account("auth-1", None) is None


@patch("app.modules.saisies_avances.application.queries.get_my_salary_advances")
@patch(
    "app.modules.saisies_avances.application.queries.resolve_employee_id_for_advance_account",
    return_value="emp-resolved",
)
def test_get_my_salary_advances_for_user_account_uses_resolved_id(
    _mock_resolve, mock_get_my
):
    mock_get_my.return_value = [{"id": "adv-1"}]
    result = get_my_salary_advances_for_user_account("auth-1", "co-1")
    mock_get_my.assert_called_once_with("emp-resolved")
    assert result == [{"id": "adv-1"}]


@patch(
    "app.modules.saisies_avances.application.queries.resolve_employee_id_for_advance_account",
    return_value=None,
)
def test_get_my_salary_advances_for_user_account_empty_when_unlinked(_mock_resolve):
    assert get_my_salary_advances_for_user_account("auth-x", "co-1") == []


@patch("app.modules.saisies_avances.application.queries.get_my_advance_available")
@patch(
    "app.modules.saisies_avances.application.queries.resolve_employee_id_for_advance_account",
    return_value="emp-resolved",
)
def test_get_my_advance_available_for_user_account_uses_resolved_id(
    _mock_resolve, mock_available
):
    mock_available.return_value = {"available_amount": 100}
    result = get_my_advance_available_for_user_account("auth-1", "co-1")
    mock_available.assert_called_once_with("emp-resolved", advance_type="avance_salaire")
    assert result == {"available_amount": 100}


@patch(
    "app.modules.saisies_avances.application.queries.resolve_employee_id_for_advance_account",
    return_value=None,
)
def test_get_my_advance_available_for_user_account_raises_when_unlinked(
    _mock_resolve,
):
    with pytest.raises(NotFoundError):
        get_my_advance_available_for_user_account("auth-x", "co-1")
