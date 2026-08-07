"""Tests unitaires des suggestions de planification d'entretiens."""

from datetime import date

from app.modules.annual_reviews.domain.campaign import InterviewCampaignSettings
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


NON_CADRE = {
    "id": "e10",
    "first_name": "Jean",
    "last_name": "Dupont",
    "statut": "Non-Cadre",
    "employment_status": "actif",
    "hire_date": "2023-04-14",
}

CAMPAGNE_NOVEMBRE = InterviewCampaignSettings(
    enabled=True, campaign_mode="mois_fixe", campaign_month=11, periodicity_years=1
)


class TestCampagneSociete:
    """Une fois la société réglée, la campagne couvre tout l'effectif, pas les seuls cadres."""

    def test_sans_reglage_le_non_cadre_reste_ignore(self):
        out = compute_planning_suggestions(
            [NON_CADRE], [], 2026, today=date(2026, 8, 7)
        )
        assert out == []

    def test_avec_reglage_le_non_cadre_est_propose(self):
        out = compute_planning_suggestions(
            [NON_CADRE], [], 2026, today=date(2026, 8, 7),
            settings=CAMPAGNE_NOVEMBRE,
        )
        assert len(out) == 1
        assert out[0]["interview_type"] == "annual_performance"
        assert out[0]["planned_date"] == "2026-11-01"
        assert out[0]["urgency"] == "due"
        assert out[0]["year"] == 2026

    def test_un_seul_entretien_propose_par_salarie(self):
        """Un cadre au forfait jour n'est pas convoqué deux fois."""
        cadre_fj = {**NON_CADRE, "id": "e11", "statut": "Cadre au forfait jour"}
        out = compute_planning_suggestions(
            [cadre_fj], [], 2026, today=date(2026, 8, 7), settings=CAMPAGNE_NOVEMBRE
        )
        assert len(out) == 1
        assert out[0]["interview_type"] == "annual_forfait_jour"

    def test_entretien_deja_couvert_rien_a_proposer(self):
        reviews = [
            {
                "employee_id": "e10",
                "interview_type": "annual_performance",
                "status": "planifie",
                "year": 2026,
            }
        ]
        out = compute_planning_suggestions(
            [NON_CADRE], reviews, 2026, today=date(2026, 8, 7),
            settings=CAMPAGNE_NOVEMBRE,
        )
        assert out == []

    def test_cycle_de_deux_ans_rien_a_proposer_avant_l_echeance(self):
        """MBC : dernier entretien 2025, cycle 2 ans -> octobre 2027, donc rien en 2026."""
        settings = InterviewCampaignSettings(
            enabled=True, campaign_mode="mois_fixe", campaign_month=10,
            periodicity_years=2,
        )
        reviews = [
            {
                "employee_id": "e10",
                "interview_type": "annual_performance",
                "status": "realise",
                "year": 2025,
            }
        ]
        out = compute_planning_suggestions(
            [NON_CADRE], reviews, 2026, today=date(2026, 8, 7), settings=settings
        )
        assert out == []

    def test_echeance_depassee_signalee_en_retard(self):
        settings = InterviewCampaignSettings(
            enabled=True, campaign_mode="mois_fixe", campaign_month=10,
            periodicity_years=2,
        )
        reviews = [
            {
                "employee_id": "e10",
                "interview_type": "annual_performance",
                "status": "realise",
                "year": 2022,
            }
        ]
        out = compute_planning_suggestions(
            [NON_CADRE], reviews, 2026, today=date(2026, 8, 7), settings=settings
        )
        assert len(out) == 1
        assert out[0]["urgency"] == "overdue"
        assert out[0]["planned_date"] == "2024-10-01"
        assert out[0]["year"] == 2024

    def test_salarie_parti_exclu_meme_avec_reglage(self):
        parti = {**NON_CADRE, "employment_status": "parti"}
        out = compute_planning_suggestions(
            [parti], [], 2026, today=date(2026, 8, 7), settings=CAMPAGNE_NOVEMBRE
        )
        assert out == []

    def test_anniversaire_embauche(self):
        settings = InterviewCampaignSettings(
            enabled=True, campaign_mode="anniversaire_embauche", periodicity_years=1
        )
        salarie = {**NON_CADRE, "hire_date": "2026-01-05"}
        out = compute_planning_suggestions(
            [salarie], [], 2027, today=date(2026, 8, 7), settings=settings
        )
        assert len(out) == 1
        assert out[0]["planned_date"] == "2027-01-05"

    def test_echeance_posterieure_a_l_annee_demandee_non_proposee(self):
        out = compute_planning_suggestions(
            [NON_CADRE], [], 2025, today=date(2026, 8, 7), settings=CAMPAGNE_NOVEMBRE
        )
        assert out == []
