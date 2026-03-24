"""
Tests unitaires du domaine annual_reviews : entités, value objects, règles, enums.

Aucune dépendance DB ni HTTP. Logique pure du domain/.
"""
from datetime import date, datetime

import pytest

from app.modules.annual_reviews.domain.entities import AnnualReview
from app.modules.annual_reviews.domain.enums import AnnualReviewStatusEnum
from app.modules.annual_reviews.domain import rules as domain_rules


# --- Entité AnnualReview ---


class TestAnnualReviewEntity:
    """Entité AnnualReview et from_row."""

    def test_from_row_builds_entity_with_required_fields(self):
        """from_row construit une entité à partir d'un dict avec champs requis."""
        row = {
            "id": "rev-1",
            "employee_id": "emp-1",
            "company_id": "co-1",
            "year": 2024,
            "status": "accepte",
        }
        entity = AnnualReview.from_row(row)
        assert entity.id == "rev-1"
        assert entity.employee_id == "emp-1"
        assert entity.company_id == "co-1"
        assert entity.year == 2024
        assert entity.status == "accepte"
        assert entity.planned_date is None
        assert entity.completed_date is None
        assert entity.created_at is None
        assert entity.updated_at is None
        assert entity.payload is row

    def test_from_row_includes_optional_dates(self):
        """from_row inclut planned_date, completed_date, created_at, updated_at si présents."""
        planned = date(2024, 6, 15)
        completed = date(2024, 6, 20)
        created = datetime(2024, 1, 1, 12, 0)
        updated = datetime(2024, 6, 20, 14, 0)
        row = {
            "id": "rev-2",
            "employee_id": "emp-2",
            "company_id": "co-2",
            "year": 2024,
            "status": "cloture",
            "planned_date": planned,
            "completed_date": completed,
            "created_at": created,
            "updated_at": updated,
        }
        entity = AnnualReview.from_row(row)
        assert entity.planned_date == planned
        assert entity.completed_date == completed
        assert entity.created_at == created
        assert entity.updated_at == updated

    def test_from_row_uses_get_for_optional_fields(self):
        """from_row utilise .get() pour les champs optionnels absents."""
        row = {
            "id": "rev-3",
            "employee_id": "emp-3",
            "company_id": "co-3",
            "year": 2025,
            "status": "en_attente_acceptation",
        }
        entity = AnnualReview.from_row(row)
        assert entity.planned_date is None
        assert entity.payload == row


# --- Enums ---


class TestAnnualReviewStatusEnum:
    """Énumération des statuts d'entretien annuel."""

    def test_all_status_values_defined(self):
        """Tous les statuts métier sont définis."""
        assert AnnualReviewStatusEnum.PLANIFIE.value == "planifie"
        assert AnnualReviewStatusEnum.EN_ATTENTE_ACCEPTATION.value == "en_attente_acceptation"
        assert AnnualReviewStatusEnum.ACCEPTE.value == "accepte"
        assert AnnualReviewStatusEnum.REFUSE.value == "refuse"
        assert AnnualReviewStatusEnum.REALISE.value == "realise"
        assert AnnualReviewStatusEnum.CLOTURE.value == "cloture"

    def test_status_required_for_mark_completed(self):
        """Constante métier : marquer comme réalisé nécessite 'accepte'."""
        assert domain_rules.STATUS_REQUIRED_FOR_MARK_COMPLETED == "accepte"

    def test_status_required_for_pdf(self):
        """Constante métier : PDF autorisé uniquement pour 'cloture'."""
        assert domain_rules.STATUS_REQUIRED_FOR_PDF == "cloture"

    def test_default_status_on_create(self):
        """Statut initial à la création."""
        assert domain_rules.DEFAULT_STATUS_ON_CREATE == "en_attente_acceptation"


# --- Règles : permissions employé / RH ---


class TestRulesEmployeePermissions:
    """Règles de permission employé."""

    def test_employee_can_update_acceptance_only_when_en_attente(self):
        """Employé peut accepter/refuser uniquement si en_attente_acceptation."""
        assert domain_rules.employee_can_update_acceptance("en_attente_acceptation") is True
        assert domain_rules.employee_can_update_acceptance("accepte") is False
        assert domain_rules.employee_can_update_acceptance("refuse") is False
        assert domain_rules.employee_can_update_acceptance("realise") is False
        assert domain_rules.employee_can_update_acceptance("cloture") is False

    def test_employee_can_update_preparation_notes_only_when_accepte(self):
        """Employé peut modifier ses notes de préparation si accepte."""
        assert domain_rules.employee_can_update_preparation_notes("accepte") is True
        assert domain_rules.employee_can_update_preparation_notes("en_attente_acceptation") is False
        assert domain_rules.employee_can_update_preparation_notes("realise") is False


class TestRulesRhPermissions:
    """Règles de permission RH."""

    def test_rh_can_edit_full_fiche_when_realise_or_cloture(self):
        """RH peut éditer la fiche complète si réalise ou clôture."""
        assert domain_rules.rh_can_edit_full_fiche("realise") is True
        assert domain_rules.rh_can_edit_full_fiche("cloture") is True
        assert domain_rules.rh_can_edit_full_fiche("accepte") is False
        assert domain_rules.rh_can_edit_full_fiche("en_attente_acceptation") is False


# --- Règles : build_employee_update_data ---


class TestBuildEmployeeUpdateData:
    """Construction du payload de mise à jour autorisé pour l'employé."""

    def test_acceptation_from_en_attente_sets_status_accepte(self):
        """En attente + employee_acceptance_status=accepte → status=accepte."""
        data = domain_rules.build_employee_update_data(
            "en_attente_acceptation",
            {"employee_acceptance_status": "accepte"},
        )
        assert data["employee_acceptance_status"] == "accepte"
        assert data["status"] == "accepte"

    def test_refus_from_en_attente_sets_status_refuse(self):
        """En attente + employee_acceptance_status=refuse → status=refuse."""
        data = domain_rules.build_employee_update_data(
            "en_attente_acceptation",
            {"employee_acceptance_status": "refuse"},
        )
        assert data["employee_acceptance_status"] == "refuse"
        assert data["status"] == "refuse"

    def test_notes_preparation_when_accepte(self):
        """Si accepte, employee_preparation_notes est autorisé."""
        data = domain_rules.build_employee_update_data(
            "accepte",
            {"employee_preparation_notes": "Mes objectifs pour l'année."},
        )
        assert data["employee_preparation_notes"] == "Mes objectifs pour l'année."

    def test_raises_value_error_when_no_allowed_update(self):
        """Lève ValueError si aucune modification autorisée."""
        with pytest.raises(ValueError) as exc_info:
            domain_rules.build_employee_update_data("accepte", {})
        assert "notes de préparation" in str(exc_info.value) or "accepter/refuser" in str(exc_info.value)

    def test_raises_value_error_when_wrong_status_for_acceptance(self):
        """En statut accepte, envoyer employee_acceptance_status ne donne pas de mise à jour employé (pas d'acceptation)."""
        with pytest.raises(ValueError):
            domain_rules.build_employee_update_data(
                "accepte",
                {"employee_acceptance_status": "accepte"},
            )

    def test_raises_value_error_when_wrong_status_for_notes(self):
        """En attente, envoyer uniquement employee_preparation_notes n'est pas autorisé (pas de clé reconnue)."""
        with pytest.raises(ValueError):
            domain_rules.build_employee_update_data(
                "en_attente_acceptation",
                {"employee_preparation_notes": "Notes"},
            )


# --- Règles : build_rh_update_data ---


class TestBuildRhUpdateData:
    """Construction du payload de mise à jour autorisé pour le RH."""

    def test_rh_can_set_planned_completed_status_template_anytime(self):
        """RH peut toujours mettre à jour planned_date, completed_date, status, rh_preparation_template."""
        data = domain_rules.build_rh_update_data(
            "en_attente_acceptation",
            {
                "planned_date": "2024-06-15",
                "completed_date": None,
                "status": "accepte",
                "rh_preparation_template": "Template RH",
            },
        )
        assert data["planned_date"] == "2024-06-15"
        assert data.get("completed_date") is None
        assert data["status"] == "accepte"
        assert data["rh_preparation_template"] == "Template RH"

    def test_rh_can_set_meeting_report_only_when_realise_or_cloture(self):
        """RH peut mettre meeting_report, rh_notes, etc. uniquement si réalise ou clôture."""
        data = domain_rules.build_rh_update_data(
            "realise",
            {
                "meeting_report": "CR entretien",
                "rh_notes": "Notes RH",
                "evaluation_summary": "RAS",
                "objectives_achieved": "Objectif 1",
                "objectives_next_year": "Objectif 2",
                "strengths": "Points forts",
                "improvement_areas": "Axes progrès",
                "training_needs": "Formation",
                "career_development": "Évolution",
                "salary_review": "Augmentation 3%",
                "overall_rating": "Très bien",
                "next_review_date": "2025-06-01",
            },
        )
        assert data["meeting_report"] == "CR entretien"
        assert data["rh_notes"] == "Notes RH"
        assert data["evaluation_summary"] == "RAS"
        assert data["objectives_next_year"] == "Objectif 2"
        assert data["next_review_date"] == "2025-06-01"

    def test_rh_fiche_fields_not_in_update_when_accepte(self):
        """En statut accepte, les champs fiche (meeting_report, etc.) ne sont pas inclus."""
        data = domain_rules.build_rh_update_data(
            "accepte",
            {"meeting_report": "CR", "planned_date": "2024-07-01"},
        )
        assert "planned_date" in data
        assert data["planned_date"] == "2024-07-01"
        assert "meeting_report" not in data

    def test_empty_data_returns_empty_dict(self):
        """Aucune clé fournie → dict vide."""
        data = domain_rules.build_rh_update_data("cloture", {})
        assert data == {}


# --- Règles : validate_can_mark_completed / validate_pdf_allowed ---


class TestValidateCanMarkCompleted:
    """Validation avant marquage comme réalisé."""

    def test_accepte_allows_mark_completed(self):
        """Statut accepte : pas d'exception."""
        domain_rules.validate_can_mark_completed("accepte")

    def test_en_attente_raises(self):
        """Statut en_attente_acceptation → ValueError."""
        with pytest.raises(ValueError) as exc_info:
            domain_rules.validate_can_mark_completed("en_attente_acceptation")
        assert "accepté par l'employé" in str(exc_info.value)

    def test_realise_raises(self):
        """Déjà réalisé → ValueError."""
        with pytest.raises(ValueError):
            domain_rules.validate_can_mark_completed("realise")


class TestValidatePdfAllowed:
    """Validation avant génération PDF."""

    def test_cloture_allows_pdf(self):
        """Statut cloture : pas d'exception."""
        domain_rules.validate_pdf_allowed("cloture")

    def test_accepte_raises(self):
        """Statut accepte → ValueError."""
        with pytest.raises(ValueError) as exc_info:
            domain_rules.validate_pdf_allowed("accepte")
        assert "clôturé" in str(exc_info.value)

    def test_realise_raises(self):
        """Statut realise → ValueError (pas encore clôturé)."""
        with pytest.raises(ValueError):
            domain_rules.validate_pdf_allowed("realise")
