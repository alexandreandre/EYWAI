"""Tests commit idempotent (mock DB)."""

from unittest.mock import MagicMock, patch

import pytest

from app.modules.dsn_import.application.commit import commit_batch


@pytest.fixture
def batch_and_items():
    batch = {
        "id": "batch-1",
        "status": "previewed",
        "summary": {},
    }
    items = [
        {
            "id": "item-g",
            "item_type": "group",
            "source_ref": "group:443061841",
            "action": "create",
            "mapped_payload": {
                "group_name": "ACME",
                "siren": "443061841",
                "description": "Import",
            },
        },
        {
            "id": "item-e",
            "item_type": "establishment",
            "source_ref": "etab:44306184100047",
            "action": "create",
            "mapped_payload": {
                "siret": "44306184100047",
                "siren": "443061841",
                "company_name": "ACME",
            },
        },
    ]
    return batch, items


def test_commit_batch_skips_scaffold_group_for_single_establishment(batch_and_items):
    batch, items = batch_and_items
    items[0]["mapped_payload"]["_scaffold"] = True
    with patch("app.modules.dsn_import.application.commit.repo") as repo, patch(
        "app.modules.dsn_import.application.commit._group_repo"
    ) as group_repo, patch(
        "app.modules.dsn_import.application.commit.get_supabase_admin_client"
    ) as client_fn:
        repo.get_batch.return_value = batch
        repo.list_items.return_value = items
        repo.find_group_by_siren.return_value = None
        repo.find_company_by_siret.return_value = None
        group_repo.create.return_value = {"id": "group-1"}
        supabase = MagicMock()
        client_fn.return_value = supabase
        supabase.table.return_value.insert.return_value.execute.return_value.data = [
            {"id": "company-1"}
        ]

        report = commit_batch("batch-1")
        assert report["stats"]["created"] == 1
        assert report["stats"]["skipped"] == 1
        assert report["group_id"] is None
        group_repo.create.assert_not_called()
        assert "44306184100047" in report["companies"]


def test_commit_batch_creates_group_for_multi_establishment():
    batch = {
        "id": "batch-2",
        "status": "previewed",
        "summary": {},
    }
    items = [
        {
            "id": "item-g",
            "item_type": "group",
            "source_ref": "group:443061841",
            "action": "create",
            "mapped_payload": {
                "group_name": "ACME",
                "siren": "443061841",
                "description": "Import",
            },
        },
        {
            "id": "item-e1",
            "item_type": "establishment",
            "source_ref": "etab:44306184100047",
            "action": "create",
            "mapped_payload": {
                "siret": "44306184100047",
                "siren": "443061841",
                "company_name": "ACME Site 1",
            },
        },
        {
            "id": "item-e2",
            "item_type": "establishment",
            "source_ref": "etab:44306184100048",
            "action": "create",
            "mapped_payload": {
                "siret": "44306184100048",
                "siren": "443061841",
                "company_name": "ACME Site 2",
            },
        },
    ]
    with patch("app.modules.dsn_import.application.commit.repo") as repo, patch(
        "app.modules.dsn_import.application.commit._group_repo"
    ) as group_repo, patch(
        "app.modules.dsn_import.application.commit.get_supabase_admin_client"
    ) as client_fn:
        repo.get_batch.return_value = batch
        repo.list_items.return_value = items
        repo.find_group_by_siren.return_value = None
        repo.find_company_by_siret.return_value = None
        group_repo.create.return_value = {"id": "group-1"}
        supabase = MagicMock()
        client_fn.return_value = supabase
        supabase.table.return_value.insert.return_value.execute.return_value.data = [
            {"id": "company-1"}
        ]

        report = commit_batch("batch-2")
        assert report["stats"]["created"] >= 3
        assert report["group_id"] == "group-1"
        group_repo.create.assert_called_once()
