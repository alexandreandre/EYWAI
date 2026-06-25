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


def test_commit_batch_clears_revocations_from_batch_period_range_without_cumuls():
    """Après purge, les révocations doivent être levées même sans item cumul commité."""
    batch = {
        "id": "batch-revoke",
        "status": "previewed",
        "period_min": "2026-02",
        "period_max": "2026-02",
        "summary": {"target_company_id": "co-1", "import_mode": "monthly"},
    }
    items = [
        {
            "id": "item-e",
            "item_type": "establishment",
            "source_ref": "etab:49861035100013",
            "action": "update",
            "mapped_payload": {
                "siret": "49861035100013",
                "siren": "498610351",
                "company_name": "Comitech",
            },
        },
    ]
    with patch("app.modules.dsn_import.application.commit.repo") as repo, patch(
        "app.modules.dsn_import.application.commit.get_supabase_admin_client"
    ) as client_fn:
        repo.get_batch.return_value = batch
        repo.list_items.return_value = items
        target_co = {"id": "co-1", "group_id": "g-1"}
        repo.find_company_by_siret.return_value = target_co
        repo.find_company_by_id.return_value = target_co
        supabase = MagicMock()
        client_fn.return_value = supabase

        commit_batch("batch-revoke")

        repo.clear_period_revocations.assert_called_once_with("co-1", ["2026-02"])


def test_commit_batch_does_not_clear_revocations_for_empty_commit():
    batch = {
        "id": "batch-empty",
        "status": "previewed",
        "period_min": "2026-01",
        "period_max": "2026-01",
        "summary": {"target_company_id": "co-1", "import_mode": "monthly"},
    }
    with patch("app.modules.dsn_import.application.commit.repo") as repo, patch(
        "app.modules.dsn_import.application.commit.get_supabase_admin_client"
    ) as client_fn:
        repo.get_batch.return_value = batch
        repo.list_items.return_value = []
        target_co = {"id": "co-1", "group_id": "g-1"}
        repo.find_company_by_id.return_value = target_co
        client_fn.return_value = MagicMock()

        commit_batch("batch-empty")

        repo.clear_period_revocations.assert_not_called()


def test_commit_batch_skips_absence_when_employee_in_exit():
    batch = {
        "id": "batch-abs-skip",
        "status": "previewed",
        "summary": {"target_company_id": "co-1"},
    }
    items = [
        {
            "id": "item-abs",
            "item_type": "absence",
            "source_ref": "abs:95147478200020:1880879329011:2026-01-05:2026-01-31:sans_solde:suspension",
            "action": "create",
            "mapped_payload": {
                "siret": "95147478200020",
                "nir": "1880879329011",
                "absence_type": "sans_solde",
                "selected_days": ["2026-01-05", "2026-01-31"],
            },
        },
    ]
    with patch("app.modules.dsn_import.application.commit.repo") as repo, patch(
        "app.modules.dsn_import.application.commit._resolve_employee_for_dsn_item",
        return_value=("emp-1", "co-1"),
    ), patch(
        "app.modules.absences.application.commands.create_reconciliation_absence",
        return_value={"skipped": True, "reason": "exit_in_progress", "employee_id": "emp-1"},
    ) as mock_absence:
        repo.get_batch.return_value = batch
        repo.list_items.return_value = items
        repo.find_company_by_id.return_value = {"id": "co-1", "group_id": "g-1"}

        report = commit_batch("batch-abs-skip")

        mock_absence.assert_called_once()
        assert report["stats"]["skipped"] == 1
        assert report["stats"]["failed"] == 0
        assert report["errors"] == []
        assert len(report["warnings"]) == 1
        assert report["warnings"][0]["code"] == "absence_blocked_by_exit"
        assert report["warnings"][0]["severity"] == "warning"


def test_commit_batch_orders_absence_before_exit():
    batch = {"id": "batch-order", "status": "previewed", "summary": {}}
    items = [
        {
            "id": "item-exit",
            "item_type": "exit",
            "source_ref": "exit:1",
            "action": "create",
            "mapped_payload": {"siret": "95147478200020", "nir": "1"},
        },
        {
            "id": "item-abs",
            "item_type": "absence",
            "source_ref": "abs:1",
            "action": "create",
            "mapped_payload": {"siret": "95147478200020", "nir": "1", "selected_days": ["2026-01-01"]},
        },
    ]
    call_order: list[str] = []

    def fake_exit(*_args, **_kwargs):
        call_order.append("exit")

    def fake_absence(*_args, **_kwargs):
        call_order.append("absence")
        return {"id": "abs-1"}

    with patch("app.modules.dsn_import.application.commit.repo") as repo, patch(
        "app.modules.dsn_import.application.commit._commit_exit",
        side_effect=fake_exit,
    ), patch(
        "app.modules.dsn_import.application.commit._commit_absence",
        side_effect=fake_absence,
    ), patch(
        "app.modules.dsn_import.application.commit._resolve_employee_for_dsn_item",
        return_value=("emp-1", "co-1"),
    ):
        repo.get_batch.return_value = batch
        repo.list_items.return_value = items

        commit_batch("batch-order")

        assert call_order == ["absence", "exit"]
