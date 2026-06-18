"""Tests réimport DSN mensuel sur période déjà couverte."""

from unittest.mock import patch

from app.modules.dsn_import.application.commit import commit_batch


def test_commit_update_employee_does_not_overwrite_employment_status():
    """Réimport : mise à jour fiche salarié sans écraser le statut RH."""
    batch = {"id": "batch-reimport", "status": "previewed", "summary": {"import_mode": "monthly"}}
    items = [
        {
            "id": "item-emp",
            "item_type": "employee",
            "source_ref": "emp:80248516900022:1770373054016",
            "action": "update",
            "mapped_payload": {
                "first_name": "Alex",
                "last_name": "Jolly",
                "nir": "1770373054016",
                "employment_status": "actif",
                "salaire_brut": 2500.0,
            },
        }
    ]
    existing = {
        "id": "emp-1",
        "company_id": "co-1",
        "nir": "1770373054016",
        "employment_status": "en_sortie",
        "employee_folder_name": "JOLLY_Alex",
    }
    with patch("app.modules.dsn_import.application.commit.repo") as repo, patch(
        "app.modules.dsn_import.application.commit.update_employee"
    ) as update_emp, patch(
        "app.modules.dsn_import.application.commit.sync_employee_psc_catalog"
    ), patch(
        "app.modules.dsn_import.application.commit.create_employee_imported"
    ) as create_emp:
        repo.get_batch.return_value = batch
        repo.list_items.return_value = items
        repo.find_company_by_siret.return_value = {"id": "co-1"}
        repo.find_employee_by_nir.return_value = existing
        repo.find_employee_by_nir_global.return_value = None
        repo.employee_has_column.return_value = True

        report = commit_batch("batch-reimport", target_company_id="co-1")

    create_emp.assert_not_called()
    update_emp.assert_called_once()
    payload = update_emp.call_args[0][1]
    assert "employment_status" not in payload
    assert report["stats"]["updated"] == 1


def test_commit_cumul_overwrites_on_reimport():
    """Réimport : les cumuls du mois sont réécrits sur disque."""
    batch = {"id": "batch-reimport-cumul", "status": "previewed", "summary": {"import_mode": "monthly"}}
    items = [
        {
            "id": "item-c",
            "item_type": "cumul",
            "source_ref": "cumul:80248516900022:1770373054016:2026-03",
            "action": "update",
            "mapped_payload": {
                "siret": "80248516900022",
                "nir": "1770373054016",
                "employee_key": "1770373054016",
                "month": 3,
                "period": "2026-03",
                "month_totals": {"brut": 3100.0},
                "cumuls_document": {"periode": {"mois": 3}},
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
            "employee_folder_name": "JOLLY_Alex",
        }
        rebuild.return_value = {"periode": {"mois": 3}, "cumuls": {"brut": 3100.0}}

        report = commit_batch("batch-reimport-cumul", target_company_id="co-1")

    rebuild.assert_called_once()
    write_file.assert_called_once_with("JOLLY_Alex", 3, rebuild.return_value)
    assert report["stats"]["updated"] == 1
