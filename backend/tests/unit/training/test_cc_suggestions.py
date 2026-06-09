"""Tests croisement propositions CC ↔ catalogue."""

from app.modules.training.application.commands import create_training_from_cc_recommendation
from app.modules.training.domain.cc_suggestions import (
    build_catalog_match_maps,
    match_recommendation_to_catalog,
    normalize_training_title,
)


class TestNormalizeTrainingTitle:
    def test_ignore_case_and_accents(self):
        assert normalize_training_title("Sécurité  SST") == normalize_training_title(
            "securite sst"
        )


class TestCatalogMatch:
    def test_match_par_reco_id_prioritaire(self):
        by_reco, by_title = build_catalog_match_maps(
            [
                {
                    "id": "t1",
                    "title": "Autre titre",
                    "source_cc_recommendation_id": "reco-1",
                }
            ]
        )
        already, tid = match_recommendation_to_catalog(
            {"id": "reco-1", "title": "Formation X"},
            by_reco=by_reco,
            by_title=by_title,
        )
        assert already is True
        assert tid == "t1"

    def test_fallback_titre_normalise(self):
        by_reco, by_title = build_catalog_match_maps(
            [{"id": "t2", "title": "Formation SST", "source_cc_recommendation_id": None}]
        )
        already, tid = match_recommendation_to_catalog(
            {"id": "reco-2", "title": "formation sst"},
            by_reco=by_reco,
            by_title=by_title,
        )
        assert already is True
        assert tid == "t2"


class TestCreateFromRecommendationMapping:
    def test_payload_catalogue_par_defaut(self, monkeypatch):
        reco = {
            "id": "reco-1",
            "idcc": "1234",
            "title": "Formation obligatoire",
            "is_active": True,
            "pedagogical_objective": "Objectif",
        }

        class FakeSvc:
            def get_recommendation(self, _id):
                return reco

        monkeypatch.setattr(
            "app.modules.collective_agreements.training_reco.service.get_cc_training_recommendations_service",
            lambda: FakeSvc(),
        )
        monkeypatch.setattr(
            "app.modules.training.infrastructure.cc_resolution.company_has_idcc",
            lambda _cid, _idcc: True,
        )
        monkeypatch.setattr(
            "app.modules.training.infrastructure.repository.training_repository.get_training_by_source_cc_recommendation",
            lambda *_a, **_k: None,
        )

        captured = {}

        def fake_create(company_id, payload):
            captured["company_id"] = company_id
            captured["payload"] = payload
            return {
                "id": "new-t",
                "company_id": company_id,
                **payload,
                "status": "active",
                "categories": payload.get("categories", []),
            }

        monkeypatch.setattr(
            "app.modules.training.infrastructure.repository.training_repository.create_training",
            fake_create,
        )

        out = create_training_from_cc_recommendation("company-1", "reco-1")
        assert out.title == "Formation obligatoire"
        assert captured["payload"]["training_type"] == "presentiel"
        assert captured["payload"]["categories"] == ["Convention collective"]
        assert captured["payload"]["source_cc_recommendation_id"] == "reco-1"
