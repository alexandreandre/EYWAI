"""Tests unitaires des suggestions de planification d'entretiens."""

from datetime import date

from app.modules.annual_reviews.domain.planning_suggestions import (
    compute_planning_suggestions,
    is_cadre,
)


class TestIsCadre:
    def test_cadre_true(self):
        assert is_cadre("Cadre") is True
        assert is_cadre("Cadre au forfait jour") is True

    def test_non_cadre_false(self):
        assert is_cadre("Non-Cadre") is False
        assert is_cadre("Non-Cadre au forfait jour") is False
        assert is_cadre(None) is False


class TestComputePlanningSuggestions:
    def test_forfait_jour_without_review(self):
        employees = [
            {
                "id": "e1",
                "first_name": "Jean",
                "last_name": "Dupont",
                "statut": "Cadre au forfait jour",
                "employment_status": "actif",
            }
        ]
        out = compute_planning_suggestions(
            employees, [], 2026, today=date(2026, 3, 1)
        )
        types = {s["interview_type"] for s in out}
        assert "annual_forfait_jour" in types
        assert "annual_cadres" in types

    def test_no_suggestion_when_review_exists(self):
        employees = [
            {
                "id": "e1",
                "first_name": "Jean",
                "last_name": "Dupont",
                "statut": "Cadre au forfait jour",
                "employment_status": "actif",
            }
        ]
        reviews = [
            {
                "employee_id": "e1",
                "interview_type": "annual_forfait_jour",
                "status": "accepte",
                "year": 2026,
            },
            {
                "employee_id": "e1",
                "interview_type": "annual_cadres",
                "status": "cloture",
                "year": 2026,
            },
        ]
        out = compute_planning_suggestions(
            employees, reviews, 2026, today=date(2026, 3, 1)
        )
        assert out == []

    def test_overdue_after_june(self):
        employees = [
            {
                "id": "e2",
                "first_name": "Marie",
                "last_name": "Martin",
                "statut": "Non-Cadre au forfait jour",
                "employment_status": "actif",
            }
        ]
        out = compute_planning_suggestions(
            employees, [], 2026, today=date(2026, 7, 1)
        )
        assert len(out) == 1
        assert out[0]["urgency"] == "overdue"

    def test_inactive_employee_excluded(self):
        employees = [
            {
                "id": "e3",
                "first_name": "Paul",
                "last_name": "Durand",
                "statut": "Cadre",
                "employment_status": "parti",
            }
        ]
        out = compute_planning_suggestions(
            employees, [], 2026, today=date(2026, 3, 1)
        )
        assert out == []
