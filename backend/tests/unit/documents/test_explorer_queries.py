"""Tests explorateur documents RH — résolution dossiers storage."""

from app.modules.documents.application.explorer_queries import (
    _resolve_visible_employee_from_folder,
)


def test_resolve_folder_by_employee_id():
    emp = {"id": "emp-1", "first_name": "Jean", "last_name": "DUPONT"}
    employees = {"emp-1": emp}
    visible = {"emp-1"}

    resolved = _resolve_visible_employee_from_folder("emp-1", employees, visible)

    assert resolved == ("emp-1", emp)


def test_resolve_folder_by_user_id():
    emp = {"id": "emp-1", "first_name": "Jean", "last_name": "DUPONT", "user_id": "user-9"}
    employees = {"emp-1": emp, "user-9": emp}
    visible = {"emp-1"}

    resolved = _resolve_visible_employee_from_folder("user-9", employees, visible)

    assert resolved == ("emp-1", emp)


def test_resolve_folder_skips_archived_employee():
    emp = {"id": "emp-1", "first_name": "Jean", "last_name": "DUPONT"}
    employees = {"emp-1": emp}
    visible: set[str] = set()

    assert _resolve_visible_employee_from_folder("emp-1", employees, visible) is None


def test_resolve_folder_unknown_name():
    emp = {"id": "emp-1", "first_name": "Jean", "last_name": "DUPONT"}
    employees = {"emp-1": emp}
    visible = {"emp-1"}

    assert _resolve_visible_employee_from_folder("unknown-folder", employees, visible) is None
