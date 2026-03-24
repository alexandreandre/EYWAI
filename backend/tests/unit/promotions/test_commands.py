"""
Tests unitaires des commandes promotions (application/commands.py).

Repositories et dépendances infra mockés ; pas de DB ni HTTP.
"""
from datetime import date, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.modules.promotions.application import commands
from app.modules.promotions.schemas import PromotionCreate, PromotionRead, PromotionUpdate


# Constantes de test
COMPANY_ID = "company-promo-test"
REQUESTED_BY = "user-rh-test"
EMPLOYEE_ID = "employee-promo-test"


def _promotion_read_draft(**kwargs):
    """PromotionRead en statut draft pour les mocks."""
    defaults = {
        "id": "promo-1",
        "company_id": COMPANY_ID,
        "employee_id": EMPLOYEE_ID,
        "promotion_type": "salaire",
        "status": "draft",
        "effective_date": date(2025, 6, 1),
        "request_date": date(2025, 3, 1),
        "previous_job_title": "Dev",
        "previous_rh_access": None,
        "new_job_title": None,
        "new_salary": {"valeur": 3800, "devise": "EUR"},
        "new_statut": None,
        "new_classification": None,
        "grant_rh_access": False,
        "new_rh_access": None,
        "reason": "Augmentation",
        "justification": None,
        "performance_review_id": None,
        "requested_by": REQUESTED_BY,
        "approved_by": None,
        "approved_at": None,
        "rejection_reason": None,
        "notes": None,
        "promotion_letter_url": None,
        "created_at": datetime(2025, 3, 1, 10, 0),
        "updated_at": datetime(2025, 3, 1, 10, 0),
    }
    defaults.update(kwargs)
    return PromotionRead(**defaults)


class TestCreatePromotionCmd:
    """Commande create_promotion_cmd."""

    @patch("app.modules.promotions.application.commands.get_promotion_repository")
    @patch("app.modules.promotions.application.commands.get_employee_snapshot_for_promotion")
    def test_creates_promotion_with_draft_status(
        self, mock_snapshot, mock_get_repo
    ):
        """Création avec effective_date future → statut draft."""
        mock_snapshot.return_value = {
            "employee": {
                "job_title": "Développeur",
                "salaire_de_base": {"valeur": 3500},
                "statut": "Cadre",
                "classification_conventionnelle": None,
            },
            "previous_rh_access": None,
        }
        mock_repo = MagicMock()
        mock_repo.create.return_value = "promo-new-id"
        mock_get_repo.return_value = mock_repo

        with patch(
            "app.modules.promotions.application.commands.get_promotion_by_id_query",
            return_value=_promotion_read_draft(id="promo-new-id", status="draft"),
        ):
            body = PromotionCreate(
                employee_id=EMPLOYEE_ID,
                promotion_type="salaire",
                new_salary={"valeur": 3800, "devise": "EUR"},
                effective_date=date.today() + timedelta(days=1),
                request_date=date.today(),
            )
            result = commands.create_promotion_cmd(
                body=body,
                company_id=COMPANY_ID,
                requested_by=REQUESTED_BY,
            )

        assert result.id == "promo-new-id"
        assert result.status == "draft"
        mock_repo.create.assert_called_once()
        call_data = mock_repo.create.call_args[0][0]
        assert call_data["company_id"] == COMPANY_ID
        assert call_data["employee_id"] == EMPLOYEE_ID
        assert call_data["status"] == "draft"
        assert call_data["promotion_type"] == "salaire"
        assert call_data["new_salary"] == {"valeur": 3800, "devise": "EUR"}

    @patch("app.modules.promotions.application.commands.get_promotion_repository")
    @patch("app.modules.promotions.application.commands.get_employee_snapshot_for_promotion")
    def test_raises_400_when_rh_transition_invalid(
        self, mock_snapshot, mock_get_repo
    ):
        """grant_rh_access avec transition non autorisée → 400."""
        mock_snapshot.return_value = {
            "employee": {"job_title": "Dev", "salaire_de_base": None, "statut": None, "classification_conventionnelle": None},
            "previous_rh_access": None,
        }
        mock_repo = MagicMock()
        mock_get_repo.return_value = mock_repo

        body = PromotionCreate(
            employee_id=EMPLOYEE_ID,
            promotion_type="salaire",
            new_salary={"valeur": 4000, "devise": "EUR"},
            effective_date=date.today(),
            request_date=date.today(),
            grant_rh_access=True,
            new_rh_access="admin",  # null → admin non autorisé
        )
        with pytest.raises(HTTPException) as exc_info:
            commands.create_promotion_cmd(
                body=body,
                company_id=COMPANY_ID,
                requested_by=REQUESTED_BY,
            )
        assert exc_info.value.status_code == 400
        assert "Transition" in exc_info.value.detail or "rôle" in exc_info.value.detail
        mock_repo.create.assert_not_called()


class TestUpdatePromotionCmd:
    """Commande update_promotion_cmd."""

    @patch("app.modules.promotions.application.commands.get_promotion_repository")
    def test_raises_404_when_promotion_not_found(self, mock_get_repo):
        """Promotion inexistante → 404."""
        mock_repo = MagicMock()
        mock_repo.get_by_id.return_value = None
        mock_get_repo.return_value = mock_repo

        body = PromotionUpdate(new_job_title="Lead Dev")
        with pytest.raises(HTTPException) as exc_info:
            commands.update_promotion_cmd(
                promotion_id="promo-unknown",
                body=body,
                company_id=COMPANY_ID,
            )
        assert exc_info.value.status_code == 404
        assert "non trouvée" in exc_info.value.detail.lower()

    @patch("app.modules.promotions.application.commands.get_promotion_repository")
    def test_raises_400_when_not_draft(self, mock_get_repo):
        """Modification d'une promotion non draft → 400."""
        mock_repo = MagicMock()
        mock_repo.get_by_id.return_value = _promotion_read_draft(status="pending_approval")
        mock_get_repo.return_value = mock_repo

        body = PromotionUpdate(new_job_title="Lead Dev")
        with pytest.raises(HTTPException) as exc_info:
            commands.update_promotion_cmd(
                promotion_id="promo-1",
                body=body,
                company_id=COMPANY_ID,
            )
        assert exc_info.value.status_code == 400
        assert "draft" in exc_info.value.detail.lower() or "statut" in exc_info.value.detail.lower()

    @patch("app.modules.promotions.application.commands.get_promotion_by_id_query")
    @patch("app.modules.promotions.application.commands.get_promotion_repository")
    def test_updates_draft_and_returns_read(
        self, mock_get_repo, mock_get_by_id
    ):
        """Mise à jour d'un draft → repo.update puis retour get_by_id."""
        mock_repo = MagicMock()
        mock_repo.get_by_id.return_value = _promotion_read_draft(status="draft")
        mock_get_repo.return_value = mock_repo
        updated_read = _promotion_read_draft(new_job_title="Lead Dev")
        mock_get_by_id.return_value = updated_read

        body = PromotionUpdate(new_job_title="Lead Dev")
        result = commands.update_promotion_cmd(
            promotion_id="promo-1",
            body=body,
            company_id=COMPANY_ID,
        )

        assert result.new_job_title == "Lead Dev"
        mock_repo.update.assert_called_once()
        call_args = mock_repo.update.call_args[0]
        assert call_args[0] == "promo-1"
        assert call_args[1] == COMPANY_ID
        assert call_args[2]["new_job_title"] == "Lead Dev"


class TestSubmitPromotionCmd:
    """Commande submit_promotion_cmd."""

    @patch("app.modules.promotions.application.commands.get_promotion_repository")
    def test_raises_404_when_not_found(self, mock_get_repo):
        """Promotion inexistante → 404."""
        mock_repo = MagicMock()
        mock_repo.get_by_id.return_value = None
        mock_get_repo.return_value = mock_repo
        with pytest.raises(HTTPException) as exc_info:
            commands.submit_promotion_cmd("promo-unknown", COMPANY_ID)
        assert exc_info.value.status_code == 404

    @patch("app.modules.promotions.application.commands.get_promotion_repository")
    def test_raises_400_when_not_draft(self, mock_get_repo):
        """Soumission d'une promotion non draft → 400."""
        mock_repo = MagicMock()
        mock_repo.get_by_id.return_value = _promotion_read_draft(status="approved")
        mock_get_repo.return_value = mock_repo
        with pytest.raises(HTTPException) as exc_info:
            commands.submit_promotion_cmd("promo-1", COMPANY_ID)
        assert exc_info.value.status_code == 400

    @patch("app.modules.promotions.application.commands.get_promotion_by_id_query")
    @patch("app.modules.promotions.application.commands.get_promotion_repository")
    def test_submits_and_returns_read(self, mock_get_repo, mock_get_by_id):
        """Draft avec au moins un champ nouveau → pending_approval."""
        mock_repo = MagicMock()
        mock_repo.get_by_id.return_value = _promotion_read_draft(
            status="draft",
            new_salary={"valeur": 4000, "devise": "EUR"},
        )
        mock_get_repo.return_value = mock_repo
        submitted = _promotion_read_draft(status="pending_approval")
        mock_get_by_id.return_value = submitted

        result = commands.submit_promotion_cmd("promo-1", COMPANY_ID)

        assert result.status == "pending_approval"
        mock_repo.update.assert_called_once_with(
            "promo-1", COMPANY_ID, {"status": "pending_approval"}
        )


class TestApprovePromotionCmd:
    """Commande approve_promotion_cmd."""

    @patch("app.modules.promotions.application.commands.get_promotion_repository")
    def test_raises_404_when_not_found(self, mock_get_repo):
        """Promotion inexistante → 404."""
        mock_repo = MagicMock()
        mock_repo.get_by_id.return_value = None
        mock_get_repo.return_value = mock_repo
        with pytest.raises(HTTPException) as exc_info:
            commands.approve_promotion_cmd(
                promotion_id="promo-unknown",
                company_id=COMPANY_ID,
                approved_by="user-admin",
            )
        assert exc_info.value.status_code == 404

    @patch("app.modules.promotions.application.commands.get_promotion_repository")
    def test_raises_400_when_not_pending_approval(self, mock_get_repo):
        """Approbation d'une promotion non pending_approval → 400."""
        mock_repo = MagicMock()
        mock_repo.get_by_id.return_value = _promotion_read_draft(status="draft")
        mock_get_repo.return_value = mock_repo
        with pytest.raises(HTTPException) as exc_info:
            commands.approve_promotion_cmd(
                promotion_id="promo-1",
                company_id=COMPANY_ID,
                approved_by="user-admin",
            )
        assert exc_info.value.status_code == 400

    @patch("app.modules.promotions.application.commands.get_promotion_document_provider")
    @patch("app.modules.promotions.application.commands.get_promotion_by_id_query")
    @patch("app.modules.promotions.application.commands.get_promotion_repository")
    def test_approves_and_updates_status(
        self, mock_get_repo, mock_get_by_id, mock_get_provider
    ):
        """pending_approval → approved, approved_by et approved_at renseignés."""
        current = _promotion_read_draft(status="pending_approval", employee_id=EMPLOYEE_ID)
        mock_repo = MagicMock()
        mock_repo.get_by_id.return_value = current
        mock_get_repo.return_value = mock_repo
        approved_read = _promotion_read_draft(
            status="approved",
            approved_by="user-admin",
            approved_at=datetime.now(),
        )
        mock_get_by_id.return_value = approved_read

        mock_provider = MagicMock()
        mock_provider.generate_letter.return_value = b"%PDF-1.4"
        mock_provider.save_document.return_value = "https://storage/promo-1.pdf"
        mock_get_provider.return_value = mock_provider

        with patch(
            "app.modules.promotions.infrastructure.queries.get_company_data_for_document",
            return_value={"company_name": "Test Co"},
        ), patch(
            "app.modules.promotions.infrastructure.queries.get_employee_data_for_document",
            return_value={"first_name": "Jean", "last_name": "Dupont", "employee_folder_name": "dupont_jean"},
        ):
            result = commands.approve_promotion_cmd(
                promotion_id="promo-1",
                company_id=COMPANY_ID,
                approved_by="user-admin",
                notes="OK",
            )

        assert result.status == "approved"
        mock_repo.update.assert_called()
        calls = mock_repo.update.call_args_list
        assert len(calls) >= 1
        first_update = calls[0][0][2]
        assert first_update["status"] == "approved"
        assert "approved_by" in first_update
        assert "approved_at" in first_update


class TestRejectPromotionCmd:
    """Commande reject_promotion_cmd."""

    @patch("app.modules.promotions.application.commands.get_promotion_repository")
    def test_raises_404_when_not_found(self, mock_get_repo):
        mock_repo = MagicMock()
        mock_repo.get_by_id.return_value = None
        mock_get_repo.return_value = mock_repo
        with pytest.raises(HTTPException) as exc_info:
            commands.reject_promotion_cmd(
                promotion_id="promo-unknown",
                company_id=COMPANY_ID,
                rejection_reason="Raison de rejet suffisamment longue",
            )
        assert exc_info.value.status_code == 404

    @patch("app.modules.promotions.application.commands.get_promotion_by_id_query")
    @patch("app.modules.promotions.application.commands.get_promotion_repository")
    def test_rejects_and_updates_status(self, mock_get_repo, mock_get_by_id):
        mock_repo = MagicMock()
        mock_repo.get_by_id.return_value = _promotion_read_draft(status="pending_approval")
        mock_get_repo.return_value = mock_repo
        rejected = _promotion_read_draft(status="rejected", rejection_reason="Budget")
        mock_get_by_id.return_value = rejected

        result = commands.reject_promotion_cmd(
            promotion_id="promo-1",
            company_id=COMPANY_ID,
            rejection_reason="Budget insuffisant pour cette période",
        )

        assert result.status == "rejected"
        mock_repo.update.assert_called_once()
        call_data = mock_repo.update.call_args[0][2]
        assert call_data["status"] == "rejected"
        assert "rejection_reason" in call_data


class TestMarkEffectivePromotionCmd:
    """Commande mark_effective_promotion_cmd."""

    @patch("app.modules.promotions.application.commands.get_promotion_repository")
    @patch("app.modules.promotions.application.commands.get_promotion_by_id_query")
    def test_raises_400_when_not_draft_or_effective(self, mock_get_by_id, mock_get_repo):
        """Marquer effective une promotion approved → 400."""
        mock_get_by_id.return_value = _promotion_read_draft(status="approved")
        mock_repo = MagicMock()
        mock_get_repo.return_value = mock_repo

        with pytest.raises(HTTPException) as exc_info:
            commands.mark_effective_promotion_cmd("promo-1", COMPANY_ID)
        assert exc_info.value.status_code == 400

    @patch("app.modules.promotions.application.commands.apply_promotion_changes")
    @patch("app.modules.promotions.application.commands.get_promotion_by_id_query")
    @patch("app.modules.promotions.application.commands.get_promotion_repository")
    def test_marks_draft_effective_and_applies_changes(
        self, mock_get_repo, mock_get_by_id, mock_apply
    ):
        """Draft → effective et apply_promotion_changes appelé."""
        draft = _promotion_read_draft(status="draft", new_salary={"valeur": 4000})
        mock_get_by_id.return_value = draft
        effective_read = _promotion_read_draft(status="effective")
        mock_get_by_id.side_effect = [draft, effective_read]

        mock_repo = MagicMock()
        mock_get_repo.return_value = mock_repo

        result = commands.mark_effective_promotion_cmd("promo-1", COMPANY_ID)

        assert result.status == "effective"
        mock_apply.assert_called_once()
        mock_repo.update.assert_called_once()
        update_data = mock_repo.update.call_args[0][2]
        assert update_data["status"] == "effective"


class TestDeletePromotionCmd:
    """Commande delete_promotion_cmd."""

    @patch("app.modules.promotions.application.commands.get_promotion_repository")
    def test_raises_404_when_not_found(self, mock_get_repo):
        mock_repo = MagicMock()
        mock_repo.get_by_id.return_value = None
        mock_get_repo.return_value = mock_repo
        with pytest.raises(HTTPException) as exc_info:
            commands.delete_promotion_cmd("promo-unknown", COMPANY_ID)
        assert exc_info.value.status_code == 404

    @patch("app.modules.promotions.application.commands.get_promotion_repository")
    def test_raises_400_when_not_draft(self, mock_get_repo):
        mock_repo = MagicMock()
        mock_repo.get_by_id.return_value = _promotion_read_draft(status="pending_approval")
        mock_get_repo.return_value = mock_repo
        with pytest.raises(HTTPException) as exc_info:
            commands.delete_promotion_cmd("promo-1", COMPANY_ID)
        assert exc_info.value.status_code == 400

    @patch("app.modules.promotions.application.commands.get_promotion_repository")
    def test_deletes_draft(self, mock_get_repo):
        mock_repo = MagicMock()
        mock_repo.get_by_id.return_value = _promotion_read_draft(status="draft")
        mock_get_repo.return_value = mock_repo

        commands.delete_promotion_cmd("promo-1", COMPANY_ID)

        mock_repo.delete.assert_called_once_with("promo-1", COMPANY_ID)
