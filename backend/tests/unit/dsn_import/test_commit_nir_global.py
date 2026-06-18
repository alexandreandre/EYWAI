"""Tests résolution salarié par NIR global + cumuls commit."""

from unittest.mock import MagicMock, patch

from app.modules.dsn_import.application.commit import commit_batch


def test_commit_employee_blocks_when_nir_exists_in_other_company():
    """Le NIR est unique globalement : pas de déplacement automatique entre entreprises."""
    batch = {"id": "batch-nir", "status": "previewed", "summary": {}}
    items = [
        {
            "id": "item-emp",
            "item_type": "employee",
            "source_ref": "emp:80248516900022:1630899139837",
            "action": "create",
            "mapped_payload": {
                "first_name": "Jean",
                "last_name": "Dupont",
                "nir": "1630899139837",
            },
        }
    ]
    existing = {
        "id": "emp-existing",
        "company_id": "old-co",
        "nir": "1630899139837",
        "employee_folder_name": "DUPONT_Jean",
    }
    with patch("app.modules.dsn_import.application.commit.repo") as repo, patch(
        "app.modules.dsn_import.application.commit.update_employee"
    ) as update_emp, patch(
        "app.modules.dsn_import.application.commit.create_employee_imported"
    ) as create_emp:
        repo.get_batch.return_value = batch
        repo.list_items.return_value = items
        repo.find_company_by_siret.return_value = {"id": "target-co"}
        repo.find_company_by_id.return_value = {"company_name": "Comitech Composite"}
        repo.find_employee_by_nir.return_value = None
        repo.find_employee_by_nir_global.return_value = existing
        repo.employee_has_column.return_value = True

        report = commit_batch("batch-nir")

    create_emp.assert_not_called()
    update_emp.assert_not_called()
    assert report["stats"]["failed"] == 1
    assert report["errors"][0]["code"] == "employee_cross_company"
    assert "Comitech Composite" in report["errors"][0]["message"]
    assert report["error_messages"]


def test_commit_cumul_calls_rebuild_on_disk():
    batch = {"id": "batch-cumul", "status": "previewed", "summary": {}}
    items = [
        {
            "id": "item-c",
            "item_type": "cumul",
            "source_ref": "cumul:80248516900022:1770373054016:2026-05",
            "action": "create",
            "mapped_payload": {
                "siret": "80248516900022",
                "nir": "1770373054016",
                "employee_key": "1770373054016",
                "month": 5,
                "period": "2026-05",
                "month_totals": {"brut": 2000.0},
                "cumuls_document": {"periode": {"mois": 5}},
            },
        }
    ]
    with patch("app.modules.dsn_import.application.commit.repo") as repo, patch(
        "app.modules.dsn_import.application.commit.rebuild_cumuls_with_previous_on_disk"
    ) as rebuild, patch(
        "app.modules.dsn_import.application.commit.write_cumuls_file"
    ) as write_file:
        repo.get_batch.return_value = batch
        repo.list_items.return_value = items
        repo.find_company_by_siret.return_value = {"id": "co-1"}
        repo.find_employee_by_nir.return_value = {
            "id": "emp-1",
            "employee_folder_name": "MARTIN_Paul",
        }
        rebuild.return_value = {"periode": {"mois": 5}, "cumuls": {}}

        report = commit_batch("batch-cumul")

    rebuild.assert_called_once()
    write_file.assert_called_once()
    assert report["stats"]["updated"] == 1
