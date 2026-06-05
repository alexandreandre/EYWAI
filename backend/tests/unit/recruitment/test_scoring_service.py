"""Tests unitaires du scoring IA recrutement."""

from unittest.mock import MagicMock, patch

import pytest

from app.modules.recruitment.application.scoring_service import (
    ScoringService,
    _apply_calibration,
    _format_opinions,
    _mention_from_score,
    _normalize_criteres,
    _weighted_score,
)


class TestScoringHelpers:
    def test_mention_from_score_bands(self):
        assert _mention_from_score(85) == "Excellent"
        assert _mention_from_score(70) == "Bon"
        assert _mention_from_score(50) == "Moyen"
        assert _mention_from_score(20) == "Faible"

    def test_weighted_score_from_criteria(self):
        criteres = {
            "competences_experience": 80,
            "formation_parcours": 70,
            "soft_skills_motivation": 60,
            "retours_interviewers": 50,
            "adequation_pratique": 40,
        }
        score = _weighted_score(criteres)
        assert score == 66

    def test_normalize_criteres_clamps(self):
        out = _normalize_criteres(
            {"competences_experience": 150, "formation_parcours": "bad"}
        )
        assert out["competences_experience"] == 100
        assert out["formation_parcours"] == 0
        assert out["soft_skills_motivation"] == 0

    def test_format_opinions_summary(self):
        text, summary = _format_opinions(
            [
                {
                    "rating": "favorable",
                    "author_first_name": "Alice",
                    "author_last_name": "Martin",
                    "created_at": "2026-01-01T10:00:00",
                    "comment": "Très bon profil",
                },
                {
                    "rating": "defavorable",
                    "author_first_name": "Bob",
                    "author_last_name": "Durand",
                    "created_at": "2026-01-02T10:00:00",
                },
            ]
        )
        assert "Favorable" in text
        assert "Défavorable" in text
        assert "1 favorable(s)" in summary
        assert "1 défavorable(s)" in summary

    def test_apply_calibration_caps_on_unanimous_negative(self):
        opinions = [
            {"rating": "defavorable"},
            {"rating": "defavorable"},
        ]
        score = _apply_calibration(
            78,
            opinions=opinions,
            has_cv=True,
            notes_count=2,
            opinions_count=2,
            interview_summaries_count=1,
        )
        assert score <= 55

    def test_apply_calibration_caps_without_data(self):
        score = _apply_calibration(
            90,
            opinions=[],
            has_cv=False,
            notes_count=0,
            opinions_count=0,
            interview_summaries_count=0,
        )
        assert score <= 40


class TestScoringService:
    @patch("app.modules.recruitment.application.scoring_service.chat_completions_create")
    @patch("app.modules.recruitment.application.scoring_service.require_llm_api_key")
    def test_score_candidate_normalizes_llm_output(self, _mock_key, mock_llm):
        mock_llm.return_value = MagicMock(
            choices=[
                MagicMock(
                    message=MagicMock(
                        content="""
                        {
                          "criteres": {
                            "competences_experience": 82,
                            "formation_parcours": 75,
                            "soft_skills_motivation": 70,
                            "retours_interviewers": 68,
                            "adequation_pratique": 80
                          },
                          "score": 99,
                          "mention": "Excellent",
                          "confiance": "Haute",
                          "points_forts": ["Expérience solide"],
                          "points_faibles": ["Mobilité à confirmer"],
                          "limites": "Analyse complète",
                          "recommandation": "Poursuivre le process"
                        }
                        """
                    )
                )
            ]
        )
        svc = ScoringService()
        result = svc.score_candidate(
            candidate={
                "first_name": "Jean",
                "last_name": "Dupont",
                "source": "LinkedIn",
                "current_stage_name": "Entretien technique",
            },
            job={
                "title": "Développeur",
                "description": "Python, React",
                "contract_type": "CDI",
                "location": "Paris",
                "tags": ["Python"],
            },
            notes=[{"content": "Bon entretien", "created_at": "2026-01-01"}],
            opinions=[{"rating": "favorable", "created_at": "2026-01-02"}],
            interviews=[
                {
                    "interview_type": "Technique",
                    "status": "done",
                    "scheduled_at": "2026-01-01",
                    "summary": "Solide sur Python",
                }
            ],
            cv_text="5 ans d'expérience Python",
            cv_status="CV extrait (PDF natif)",
        )

        assert 70 <= result["score"] <= 85
        assert result["mention"] in ("Excellent", "Bon")
        assert result["confiance"] == "Haute"
        assert result["points_forts"]
        assert result["sources"]["cv"] is True

    @patch("app.modules.recruitment.application.scoring_service.chat_completions_create")
    @patch("app.modules.recruitment.application.scoring_service.require_llm_api_key")
    def test_score_candidate_retries_on_failure(self, _mock_key, mock_llm):
        ok = MagicMock(
            choices=[MagicMock(message=MagicMock(content='{"score": 55, "mention": "Moyen", "confiance": "Faible", "criteres": {}, "points_forts": [], "points_faibles": [], "limites": "Peu de données", "recommandation": "Compléter"}'))]
        )
        mock_llm.side_effect = [RuntimeError("timeout"), ok]
        svc = ScoringService()
        result = svc.score_candidate(
            candidate={"first_name": "A", "last_name": "B"},
            job={"title": "Poste"},
            notes=[{"content": "Note test", "created_at": "2026-01-01"}],
            opinions=[],
            cv_text="Profil développeur",
        )
        assert result["score"] == 55
        assert mock_llm.call_count == 2
