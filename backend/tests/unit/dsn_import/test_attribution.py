"""Tests détection salariés déjà présents + rattachement entreprise existante."""

from unittest.mock import MagicMock, patch


from app.modules.dsn_import.application.commit import commit_batch
from app.modules.dsn_import.application.service import (
    _employee_state_counts,
    _enrich_actions,
)


def test_enrich_actions_existing_employee_defaults_to_skip():
    """Un salarié déjà présent (par NIR) ne doit pas être réécrit : action 'skip'."""
    items = [
        {
            "item_type": "employee",
            "source_ref": "emp:44306184100047:NIR1",
            "mapped_payload": {"nir": "NIR1"},
            "action": "create",
        }
    ]
    with patch("app.modules.dsn_import.application.service.repo") as repo:
        repo.find_company_by_id.return_value = None
        repo.find_company_by_siret.return_value = {"id": "co-1"}
        repo.find_employee_by_nir.return_value = {"id": "emp-1"}

        _enrich_actions(items)

    assert items[0]["action"] == "skip"
    assert items[0]["is_existing"] is True
    assert items[0]["existing_employee_id"] == "emp-1"


def test_enrich_actions_new_employee_stays_create():
    items = [
        {
            "item_type": "employee",
            "source_ref": "emp:44306184100047:NIR2",
            "mapped_payload": {"nir": "NIR2"},
            "action": "create",
        }
    ]
    with patch("app.modules.dsn_import.application.service.repo") as repo:
        repo.find_company_by_id.return_value = None
        repo.find_company_by_siret.return_value = {"id": "co-1"}
        repo.find_employee_by_nir.return_value = None
        repo.find_employee_by_nir_global.return_value = None

        _enrich_actions(items)

    assert items[0]["action"] == "create"
    assert items[0]["is_existing"] is False


def test_enrich_actions_uses_target_company_for_employee_lookup():
    """Avec une entreprise cible, la détection se fait dans cette entreprise."""
    items = [
        {
            "item_type": "establishment",
            "source_ref": "etab:44306184100047",
            "mapped_payload": {"siret": "44306184100047"},
            "action": "create",
        },
        {
            "item_type": "employee",
            "source_ref": "emp:99999999900099:NIR1",
            "mapped_payload": {"nir": "NIR1"},
            "action": "create",
        },
    ]
    with patch("app.modules.dsn_import.application.service.repo") as repo:
        repo.find_company_by_id.return_value = {"id": "target-co"}
        repo.find_employee_by_nir.return_value = None
        repo.find_employee_by_nir_global.return_value = None

        _enrich_actions(items, target_company_id="target-co")

    # L'établissement est marqué "update" (rattachement à l'existant)
    assert items[0]["action"] == "update"
    # Lookup salarié réalisé dans l'entreprise cible
    repo.find_employee_by_nir.assert_called_once_with("target-co", "NIR1")


def test_enrich_actions_detects_employee_by_global_nir():
    """Un NIR déjà présent dans une autre entreprise est détecté comme existant."""
    items = [
        {
            "item_type": "employee",
            "source_ref": "emp:44306184100047:NIR1",
            "mapped_payload": {"nir": "NIR1", "first_name": "Jean", "last_name": "Martin"},
            "label": "Jean Martin",
            "action": "create",
        }
    ]
    anomalies: list = []
    with patch("app.modules.dsn_import.application.service.repo") as repo:
        repo.find_company_by_id.side_effect = lambda cid: (
            {"id": "target-co", "company_name": "Colorplast"}
            if cid == "target-co"
            else {"id": "other-co", "company_name": "Comitech Composite"}
        )
        repo.find_employee_by_nir.return_value = None
        repo.find_employee_by_nir_global.return_value = {
            "id": "emp-global",
            "company_id": "other-co",
        }

        _enrich_actions(items, target_company_id="target-co", anomalies=anomalies)

    assert items[0]["action"] == "skip"
    assert items[0]["is_existing"] is True
    assert items[0]["existing_company_name"] == "Comitech Composite"
    assert any(a.get("code") == "employee_other_company" for a in anomalies)


def test_employee_state_counts():
    items = [
        {"item_type": "employee", "is_existing": True},
        {"item_type": "employee", "is_existing": False},
        {"item_type": "employee", "is_existing": True},
        {"item_type": "group"},
    ]
    counts = _employee_state_counts(items)
    assert counts == {"employee_existing_count": 2, "employee_new_count": 1}


def test_commit_with_target_company_attaches_without_creating():
    """Le rattachement n'écrase pas l'entreprise et n'en crée pas de nouvelle."""
    batch = {"id": "batch-1", "status": "previewed", "summary": {}}
    items = [
        {
            "id": "item-g",
            "item_type": "group",
            "source_ref": "group:443061841",
            "action": "create",
            "mapped_payload": {"siren": "443061841", "group_name": "ACME"},
        },
        {
            "id": "item-e",
            "item_type": "establishment",
            "source_ref": "etab:44306184100047",
            "action": "create",
            "mapped_payload": {"siret": "44306184100047", "company_name": "ACME"},
        },
        {
            "id": "item-emp",
            "item_type": "employee",
            "source_ref": "emp:44306184100047:NIR1",
            "action": "create",
            "mapped_payload": {"first_name": "Jean", "last_name": "Martin", "nir": "NIR1"},
        },
    ]
    with patch("app.modules.dsn_import.application.commit.repo") as repo, patch(
        "app.modules.dsn_import.application.commit._group_repo"
    ) as group_repo, patch(
        "app.modules.dsn_import.application.commit.get_supabase_admin_client"
    ) as client_fn, patch(
        "app.modules.dsn_import.application.commit.create_employee_imported"
    ) as create_emp:
        repo.get_batch.return_value = batch
        repo.list_items.return_value = items
        repo.find_company_by_id.return_value = {"id": "target-co", "group_id": "grp-1"}
        repo.find_employee_by_nir.return_value = None
        repo.find_employee_by_nir_global.return_value = None
        repo.employee_has_column.return_value = True
        create_emp.return_value = {
            "id": "emp-new",
            "company_id": "target-co",
            "user_id": None,
            "first_name": "Jean",
            "last_name": "Martin",
        }
        client_fn.return_value = MagicMock()

        report = commit_batch("batch-1", target_company_id="target-co")

    # Aucune création de groupe ni d'entreprise
    group_repo.create.assert_not_called()
    # Le salarié est rattaché à l'entreprise cible
    create_emp.assert_called_once()
    assert create_emp.call_args[0][1] == "target-co"
    # L'établissement de la DSN pointe vers l'entreprise cible
    assert report["companies"]["44306184100047"] == "target-co"
    assert report["target_company_id"] == "target-co"
    assert report["group_id"] == "grp-1"
    assert report["stats"]["skipped"] >= 1  # le groupe


def test_commit_skips_existing_employee_without_rewrite():
    """Un salarié en action 'skip' n'est pas mis à jour."""
    batch = {"id": "batch-2", "status": "previewed", "summary": {}}
    items = [
        {
            "id": "item-emp",
            "item_type": "employee",
            "source_ref": "emp:44306184100047:NIR1",
            "action": "skip",
            "mapped_payload": {"first_name": "Jean", "last_name": "Martin", "nir": "NIR1"},
        }
    ]
    with patch("app.modules.dsn_import.application.commit.repo") as repo, patch(
        "app.modules.dsn_import.application.commit.update_employee"
    ) as update_emp, patch(
        "app.modules.dsn_import.application.commit.create_employee_imported"
    ) as create_emp:
        repo.get_batch.return_value = batch
        repo.list_items.return_value = items

        report = commit_batch("batch-2")

    update_emp.assert_not_called()
    create_emp.assert_not_called()
    assert report["stats"]["skipped"] == 1
