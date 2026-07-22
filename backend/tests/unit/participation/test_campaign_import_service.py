"""Tests unitaires — service d'import des participations depuis les saisies.

Repository et Supabase mockés ; pas de DB réelle.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.modules.participation.application.campaign_import_service import (
    delete_imported_campaign,
    import_campaign_from_inputs,
)

COMPANY_ID = "550e8400-e29b-41d4-a716-446655440000"
CAMPAIGN_ID = "880e8400-e29b-41d4-a716-446655440003"


def _rows_two_employees():
    return [
        {
            "id": "r1",
            "employee_id": "e1",
            "name": "Participation 2025 — numéraire",
            "amount": 3535.86,
        },
        {
            "id": "r2",
            "employee_id": "e1",
            "name": "Avance participation 2025 (déjà versée)",
            "amount": -1000.0,
        },
        {
            "id": "r3",
            "employee_id": "e2",
            "name": "Participation 2025 — PEE",
            "amount": 5331.56,
        },
    ]


def _mock_fetch(mock_supabase, rows):
    chain = (
        mock_supabase.table.return_value.select.return_value.eq.return_value
        .eq.return_value.eq.return_value
    )
    chain.execute.return_value = MagicMock(data=rows)


def _mock_update(mock_supabase):
    update_return = mock_supabase.table.return_value.update.return_value
    update_return.in_.return_value.execute.return_value = MagicMock(data=[])
    update_return.eq.return_value.execute.return_value = MagicMock(data=[])


@pytest.fixture
def mock_supabase():
    with patch(
        "app.modules.participation.application.campaign_import_service.supabase"
    ) as supabase:
        yield supabase


@pytest.fixture
def mock_repo():
    with patch(
        "app.modules.participation.application.campaign_import_service.campaign_repository"
    ) as repo:
        repo.list_campaigns.return_value = []
        yield repo


class TestDryRun:
    def test_returns_preview_without_writing(self, mock_supabase, mock_repo):
        _mock_fetch(mock_supabase, _rows_two_employees())

        result = import_campaign_from_inputs(COMPANY_ID, 2025, 2026, 5, dry_run=True)

        assert result.dry_run is True
        assert result.bulletins == 2
        assert result.full_cash == 1
        assert result.full_pee == 1
        mock_repo.create_campaign.assert_not_called()
        mock_repo.insert_bulletins.assert_not_called()


class TestNoData:
    def test_no_participation_inputs_returns_empty_result(
        self, mock_supabase, mock_repo
    ):
        _mock_fetch(mock_supabase, [])

        result = import_campaign_from_inputs(COMPANY_ID, 2025, 2026, 5)

        assert result.bulletins == 0
        assert result.campaign_id is None
        mock_repo.create_campaign.assert_not_called()


class TestFullImport:
    def test_creates_campaign_bulletins_and_links_inputs(
        self, mock_supabase, mock_repo
    ):
        _mock_fetch(mock_supabase, _rows_two_employees())
        _mock_update(mock_supabase)
        mock_repo.create_campaign.return_value = {"id": CAMPAIGN_ID}
        mock_repo.insert_bulletins.return_value = [
            {"id": "b1", "employee_id": "e1"},
            {"id": "b2", "employee_id": "e2"},
        ]

        result = import_campaign_from_inputs(
            COMPANY_ID, 2025, 2026, 5, created_by="user-1"
        )

        assert result.campaign_id == CAMPAIGN_ID
        assert result.bulletins == 2
        assert result.linked_inputs == 3  # r1+r2 (e1) + r3 (e2)

        created_payload = mock_repo.create_campaign.call_args[0][0]
        assert created_payload["status"] == "closed"
        assert created_payload["year"] == 2025
        assert created_payload["created_by"] == "user-1"

        bulletin_rows = mock_repo.insert_bulletins.call_args[0][0]
        assert {r["employee_id"] for r in bulletin_rows} == {"e1", "e2"}
        assert all(r["status"] == "responded" for r in bulletin_rows)

        # Invariant de sécurité : le rattachement des saisies ne touche QUE les
        # colonnes de liaison — jamais amount/is_socially_taxed/is_taxable.
        update_calls = mock_supabase.table.return_value.update.call_args_list
        assert len(update_calls) == 2  # un appel par bulletin créé (e1, e2)
        for call in update_calls:
            payload = call.args[0]
            assert set(payload.keys()) == {
                "participation_campaign_id",
                "participation_bulletin_id",
            }


class TestIdempotence:
    def test_skips_when_campaign_already_imported_without_force(
        self, mock_supabase, mock_repo
    ):
        mock_repo.list_campaigns.return_value = [{"id": CAMPAIGN_ID, "year": 2025}]
        mock_repo.count_bulletins_by_status.return_value = {"responded": 5}

        result = import_campaign_from_inputs(COMPANY_ID, 2025, 2026, 5)

        assert result.skipped is True
        assert result.bulletins == 5
        mock_repo.delete_campaign.assert_not_called()
        mock_repo.create_campaign.assert_not_called()

    def test_replaces_empty_draft_without_force(self, mock_supabase, mock_repo):
        mock_repo.list_campaigns.return_value = [{"id": CAMPAIGN_ID, "year": 2025}]
        mock_repo.count_bulletins_by_status.return_value = {}
        _mock_fetch(mock_supabase, _rows_two_employees())
        _mock_update(mock_supabase)
        mock_repo.create_campaign.return_value = {"id": "new-campaign"}
        mock_repo.insert_bulletins.return_value = [
            {"id": "b1", "employee_id": "e1"},
            {"id": "b2", "employee_id": "e2"},
        ]

        result = import_campaign_from_inputs(COMPANY_ID, 2025, 2026, 5)

        mock_repo.delete_campaign.assert_called_once_with(CAMPAIGN_ID, COMPANY_ID)
        assert "brouillon" in result.detail
        assert result.campaign_id == "new-campaign"

    def test_force_replaces_existing_campaign(self, mock_supabase, mock_repo):
        mock_repo.list_campaigns.return_value = [{"id": CAMPAIGN_ID, "year": 2025}]
        mock_repo.count_bulletins_by_status.return_value = {"responded": 5}
        _mock_fetch(mock_supabase, _rows_two_employees())
        _mock_update(mock_supabase)
        mock_repo.create_campaign.return_value = {"id": "new-campaign"}
        mock_repo.insert_bulletins.return_value = [
            {"id": "b1", "employee_id": "e1"},
            {"id": "b2", "employee_id": "e2"},
        ]

        result = import_campaign_from_inputs(COMPANY_ID, 2025, 2026, 5, force=True)

        mock_repo.delete_campaign.assert_called_once_with(CAMPAIGN_ID, COMPANY_ID)
        assert result.campaign_id == "new-campaign"


class TestDeleteImportedCampaign:
    def test_unlinks_inputs_then_deletes_campaign(self, mock_supabase, mock_repo):
        _mock_update(mock_supabase)

        delete_imported_campaign(CAMPAIGN_ID, COMPANY_ID)

        update_return = mock_supabase.table.return_value.update.return_value
        update_return.eq.assert_called_once_with(
            "participation_campaign_id", CAMPAIGN_ID
        )
        mock_repo.delete_campaign.assert_called_once_with(CAMPAIGN_ID, COMPANY_ID)
