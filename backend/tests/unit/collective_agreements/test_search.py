"""Tests recherche catalogue conventions collectives."""

from app.modules.collective_agreements.domain.search import (
    filter_and_rank_agreements,
    matches_agreement_search,
    normalize_search_text,
    rank_agreement_search,
)


def _sample_agreements():
    return [
        {
            "id": "1",
            "name": "Convention collective nationale de la plasturgie",
            "idcc": "1297",
            "sector": "Plasturgie",
            "description": "Industrie des plastiques",
        },
        {
            "id": "2",
            "name": "Convention collective Syntec",
            "idcc": "1486",
            "sector": "Informatique",
            "description": "Bureaux d'études",
        },
    ]


class TestCollectiveAgreementSearch:
    def test_normalize_search_text_strips_accents(self):
        assert normalize_search_text("Plasturgie Électronique") == "plasturgie electronique"

    def test_matches_sector_keyword(self):
        agreements = _sample_agreements()
        assert matches_agreement_search(agreements[0], "plasturgie")
        assert matches_agreement_search(agreements[1], "informatique")

    def test_matches_all_tokens(self):
        agreements = _sample_agreements()
        assert matches_agreement_search(agreements[0], "industrie plastiques")
        assert not matches_agreement_search(agreements[0], "industrie syntec")

    def test_rank_prefers_idcc_exact_match(self):
        agreements = _sample_agreements()
        ranked = filter_and_rank_agreements(agreements, "1486")
        assert ranked[0]["idcc"] == "1486"
        assert rank_agreement_search(agreements[1], "1486") > rank_agreement_search(
            agreements[0], "1486"
        )

    def test_filter_and_rank_limits_results(self):
        agreements = _sample_agreements()
        ranked = filter_and_rank_agreements(agreements, "convention", limit=1)
        assert len(ranked) == 1
