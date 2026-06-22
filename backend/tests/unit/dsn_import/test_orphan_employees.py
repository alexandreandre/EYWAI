"""Tests détection / suppression salariés fantômes DSN."""

from unittest.mock import patch

from app.modules.dsn_import.application.orphan_employees import (
    compute_reimport_orphans,
    remove_reimport_orphans,
)


def test_compute_reimport_orphans_detects_placeholder_not_in_dsn():
    items = [
        {
            "item_type": "employee",
            "mapped_payload": {"nir": "1770373054016"},
        }
    ]
    with patch("app.modules.dsn_import.application.orphan_employees.repo") as repo:
        repo.list_dsn_placeholder_employees.return_value = [
            {
                "id": "ghost-1",
                "first_name": "Fantome",
                "last_name": "Import",
                "nir": "1999999999999",
                "user_id": None,
                "email": "import.fantome.123456@802485169.dsn-import.local",
            },
            {
                "id": "keep-1",
                "first_name": "Alex",
                "last_name": "Jolly",
                "nir": "1770373054016",
                "user_id": None,
                "email": "import.alex.jolly@802485169.dsn-import.local",
            },
        ]
        result = compute_reimport_orphans(items, "co-1")

    assert result["count"] == 1
    assert result["employees"][0]["employee_id"] == "ghost-1"
    assert result["employees"][0]["employee_name"] == "Fantome Import"


def test_remove_reimport_orphans_calls_delete():
    items = [{"item_type": "employee", "mapped_payload": {"nir": "111"}}]
    with patch("app.modules.dsn_import.application.orphan_employees.repo") as repo, patch(
        "app.modules.employees.application.commands.delete_employee"
    ) as delete_emp:
        repo.list_dsn_placeholder_employees.return_value = [
            {
                "id": "ghost-1",
                "first_name": "A",
                "last_name": "B",
                "nir": "222",
                "user_id": None,
                "email": "x@802485169.dsn-import.local",
            }
        ]
        report = remove_reimport_orphans(items, "co-1")

    delete_emp.assert_called_once_with("ghost-1", "co-1")
    assert report["removed_count"] == 1
    assert report["failed"] == []
