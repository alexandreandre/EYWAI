"""Tests extraction et persistance propositions formation CC."""

from unittest.mock import MagicMock, patch

import pytest

from app.modules.collective_agreements.training_reco.repository import (
    CcTrainingRecommendationsRepository,
)
from app.modules.collective_agreements.training_reco.schema import parse_extraction_result


class TestParseExtractionResult:
    def test_normalise_et_dedupe_par_titre(self):
        data = {
            "idcc": "1234",
            "formations": [
                {
                    "title": " SST ",
                    "obligation_level": "obligatoire",
                    "pedagogical_objective": "Prévention",
                    "legal_reference": "Art. 5",
                    "target_roles": ["Ouvriers"],
                    "periodicity": "3 ans",
                },
                {
                    "title": "sst",
                    "obligation_level": "recommandee",
                    "pedagogical_objective": None,
                    "legal_reference": None,
                    "target_roles": [],
                    "periodicity": None,
                },
            ],
        }
        doc = parse_extraction_result(data, expected_idcc="1234")
        assert doc.idcc == "1234"
        assert len(doc.formations) == 1
        assert doc.formations[0].title == "SST"
        assert doc.formations[0].obligation_level == "obligatoire"


class TestUpsertAiRecommendations:
    @patch.object(CcTrainingRecommendationsRepository, "list_by_idcc")
    @patch("app.modules.collective_agreements.training_reco.repository.supabase")
    def test_preserve_is_active_et_remplace_ai(self, mock_supabase, mock_list):
        mock_list.side_effect = [
            [
                {
                    "id": "old-1",
                    "title": "Formation A",
                    "source": "ai",
                    "is_active": False,
                },
            ],
            [{"id": "new-1", "title": "Formation A"}],
        ]

        table = MagicMock()
        mock_supabase.table.return_value = table
        delete_chain = MagicMock()
        delete_chain.eq.return_value = delete_chain
        delete_chain.execute.return_value = MagicMock(data=[])
        insert_chain = MagicMock()
        insert_chain.execute.return_value = MagicMock(data=[{"id": "new-1"}])
        table.delete.return_value = delete_chain
        table.insert.return_value = insert_chain

        repo = CcTrainingRecommendationsRepository()
        rows = repo.upsert_ai_recommendations(
            idcc="1234",
            agreement_id="ag-1",
            items=[
                {
                    "title": "Formation A",
                    "obligation_level": "obligatoire",
                    "pedagogical_objective": "Obj",
                    "legal_reference": "Art. 1",
                    "target_roles": [],
                    "periodicity": None,
                }
            ],
            extraction_model="test-model",
        )

        assert rows == [{"id": "new-1", "title": "Formation A"}]
        insert_payload = table.insert.call_args[0][0][0]
        assert insert_payload["is_active"] is False
        assert insert_payload["source"] == "ai"
        delete_chain.eq.assert_any_call("source", "ai")
