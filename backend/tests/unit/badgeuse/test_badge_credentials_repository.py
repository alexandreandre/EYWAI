"""Garde-fous sur les réponses Supabase maybe_single / mutations."""

from types import SimpleNamespace

from app.modules.badgeuse.infrastructure import badge_credentials_repository as repo


def test_maybe_single_row_when_execute_returns_none():
    assert repo._maybe_single_row(None) is None


def test_maybe_single_row_when_data_is_none():
    assert repo._maybe_single_row(SimpleNamespace(data=None)) is None


def test_maybe_single_row_returns_dict():
    row = {"id": "1", "employee_id": "e1"}
    assert repo._maybe_single_row(SimpleNamespace(data=row)) == row


def test_first_mutation_row_from_list():
    row = {"id": "1"}
    assert repo._first_mutation_row(SimpleNamespace(data=[row])) == row
