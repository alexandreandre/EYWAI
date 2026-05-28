"""Résolution employé ↔ compte utilisateur (espace collaborateur)."""

from unittest.mock import MagicMock, patch

from app.modules.employees.infrastructure.queries import (
    resolve_employee_id_for_user_account,
)


def _mock_execute(data):
    result = MagicMock()
    result.data = data
    return result


@patch("app.modules.employees.infrastructure.queries.supabase")
def test_resolve_by_user_id_column(mock_supabase):
    table = MagicMock()
    mock_supabase.table.return_value = table
    chain = table.select.return_value
    chain.eq.return_value = chain
    chain.maybe_single.return_value.execute.side_effect = [
        _mock_execute({"id": "emp-uuid"}),
    ]

    assert (
        resolve_employee_id_for_user_account("user-1", "co-1") == "emp-uuid"
    )
    chain.eq.assert_any_call("user_id", "user-1")


@patch("app.modules.employees.infrastructure.queries.supabase")
def test_resolve_fallback_when_id_equals_auth_uid(mock_supabase):
    table = MagicMock()
    mock_supabase.table.return_value = table
    chain = table.select.return_value
    chain.eq.return_value = chain
    chain.maybe_single.return_value.execute.side_effect = [
        _mock_execute(None),
        _mock_execute({"id": "user-1"}),
    ]

    assert resolve_employee_id_for_user_account("user-1", "co-1") == "user-1"
    chain.eq.assert_any_call("id", "user-1")


@patch("app.modules.employees.infrastructure.queries._resolve_employee_id_by_auth_email")
@patch("app.modules.employees.infrastructure.queries.supabase")
def test_resolve_by_email_fallback(mock_supabase, mock_email_resolve):
    table = MagicMock()
    mock_supabase.table.return_value = table
    chain = table.select.return_value
    chain.eq.return_value = chain
    chain.maybe_single.return_value.execute.side_effect = [
        _mock_execute(None),
        _mock_execute(None),
    ]
    mock_email_resolve.return_value = "emp-by-email"

    assert (
        resolve_employee_id_for_user_account("user-1", "co-1") == "emp-by-email"
    )
    mock_email_resolve.assert_called_once_with("user-1", "co-1")


@patch("app.modules.employees.infrastructure.queries._resolve_employee_id_by_auth_email", return_value=None)
@patch("app.modules.employees.infrastructure.queries.supabase")
def test_resolve_returns_none_when_not_found(mock_supabase, _mock_email):
    table = MagicMock()
    mock_supabase.table.return_value = table
    chain = table.select.return_value
    chain.eq.return_value = chain
    chain.maybe_single.return_value.execute.side_effect = [
        _mock_execute(None),
        _mock_execute(None),
    ]

    assert resolve_employee_id_for_user_account("user-x", "co-1") is None
