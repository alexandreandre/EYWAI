"""Tests d'intégration — ParticipationCampaignRepository.delete_campaign.

Sans DB réelle : mock Supabase pour valider les appels. Note : la suppression
d'une campagne cascade en base (FK ON DELETE CASCADE) vers ses bulletins et
avances — pas de méthode dédiée nécessaire pour ces sous-tables.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.modules.participation.infrastructure.campaign_repository import (
    ParticipationCampaignRepository,
)

pytestmark = pytest.mark.integration

COMPANY_ID = "550e8400-e29b-41d4-a716-446655440000"
CAMPAIGN_ID = "880e8400-e29b-41d4-a716-446655440003"


class TestDeleteCampaign:
    def test_delete_campaign_scopes_by_company(self):
        with patch(
            "app.modules.participation.infrastructure.campaign_repository.supabase"
        ) as supabase:
            table = MagicMock()
            delete_chain = MagicMock()
            eq_chain_1 = MagicMock()
            eq_chain_2 = MagicMock()
            table.delete.return_value = delete_chain
            delete_chain.eq.return_value = eq_chain_1
            eq_chain_1.eq.return_value = eq_chain_2
            eq_chain_2.execute.return_value = MagicMock(data=[{"id": CAMPAIGN_ID}])
            supabase.table.return_value = table

            repo = ParticipationCampaignRepository()
            repo.delete_campaign(CAMPAIGN_ID, COMPANY_ID)

            supabase.table.assert_any_call("participation_campaigns")
            table.delete.assert_called_once()
            delete_chain.eq.assert_called_once_with("id", CAMPAIGN_ID)
            eq_chain_1.eq.assert_called_once_with("company_id", COMPANY_ID)
            eq_chain_2.execute.assert_called_once()
