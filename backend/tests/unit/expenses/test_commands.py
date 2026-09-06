"""
Tests unitaires des commandes expenses (application/commands.py).

Chaque commande est testée avec le repository mocké (patch ExpenseRepository).
"""

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from app.modules.expenses.application.commands import (
    create_expense,
    update_expense_status,
)
from app.modules.expenses.application.dto import (
    CreateExpenseInput,
    UpdateExpenseStatusInput,
)


class TestCreateExpense:
    """Commande create_expense."""

    def test_create_expense_calls_repo_create_with_payload(self):
        input_ = CreateExpenseInput(
            employee_id="emp-001",
            date=date(2025, 3, 15),
            amount=55.00,
            vat_rate=10.0,
            type="Restaurant",
            description="Déjeuner client",
            receipt_url="emp-001/2025-03-15-ticket.pdf",
            filename="ticket.pdf",
        )
        created_row = {
            "id": "exp-new-1",
            "employee_id": "emp-001",
            "date": "2025-03-15",
            "amount": 55.0,
            "type": "Restaurant",
            "status": "pending",
            "description": "Déjeuner client",
            "receipt_url": "emp-001/2025-03-15-ticket.pdf",
            "filename": "ticket.pdf",
        }
        mock_repo = MagicMock()
        mock_repo.create.return_value = created_row

        with patch(
            "app.modules.expenses.application.commands.ExpenseRepository",
            return_value=mock_repo,
        ):
            result = create_expense(input_)

        mock_repo.create.assert_called_once()
        call_payload = mock_repo.create.call_args[0][0]
        assert call_payload["employee_id"] == "emp-001"
        assert call_payload["date"] == "2025-03-15"
        assert call_payload["amount"] == 55.0
        assert call_payload["vat_rate"] == 10.0
        assert call_payload["amount_ht"] == 50.0
        assert call_payload["vat_amount"] == 5.0
        assert call_payload["type"] == "Restaurant"
        assert call_payload["status"] == "pending"
        assert call_payload["description"] == "Déjeuner client"
        assert call_payload["receipt_url"] == "emp-001/2025-03-15-ticket.pdf"
        assert call_payload["filename"] == "ticket.pdf"
        assert result == created_row
        assert result["id"] == "exp-new-1"

    def test_indemnites_kilometriques_tva_forcee_a_zero(self):
        """Les IK (barème) sont hors champ TVA : taux forcé serveur, même si
        le client envoie 20 % — le TTC devient le HT, TVA nulle."""
        input_ = CreateExpenseInput(
            employee_id="emp-001",
            date=date(2026, 9, 1),
            amount=120.0,
            vat_rate=20.0,
            type="Indemnités kilométriques",
            description="Déplacements chantier",
            receipt_url="emp-001/ik.pdf",
            filename="ik.pdf",
        )
        mock_repo = MagicMock()
        mock_repo.create.return_value = {"id": "exp-ik"}

        with patch(
            "app.modules.expenses.application.commands.ExpenseRepository",
            return_value=mock_repo,
        ):
            create_expense(input_)

        call_payload = mock_repo.create.call_args[0][0]
        assert call_payload["vat_rate"] == 0.0
        assert call_payload["amount_ht"] == 120.0
        assert call_payload["vat_amount"] == 0.0

    def test_create_expense_without_optional_fields(self):
        input_ = CreateExpenseInput(
            employee_id="emp-002",
            date=date(2025, 3, 10),
            amount=30.0,
            vat_rate=20.0,
            type="Transport",
        )
        created_row = {
            "id": "exp-new-2",
            "employee_id": "emp-002",
            "date": "2025-03-10",
            "amount": 30.0,
            "type": "Transport",
            "status": "pending",
            "description": None,
            "receipt_url": None,
            "filename": None,
        }
        mock_repo = MagicMock()
        mock_repo.create.return_value = created_row

        with patch(
            "app.modules.expenses.application.commands.ExpenseRepository",
            return_value=mock_repo,
        ):
            result = create_expense(input_)

        call_payload = mock_repo.create.call_args[0][0]
        assert call_payload["description"] is None
        assert call_payload["receipt_url"] is None
        assert call_payload["filename"] is None
        assert result["status"] == "pending"

    def test_create_expense_repo_raises_propagates(self):
        input_ = CreateExpenseInput(
            employee_id="emp-003",
            date=date(2025, 3, 1),
            amount=10.0,
            vat_rate=20.0,
            type="Fournitures",
        )
        mock_repo = MagicMock()
        mock_repo.create.side_effect = ValueError(
            "Échec de la création de la note de frais."
        )

        with patch(
            "app.modules.expenses.application.commands.ExpenseRepository",
            return_value=mock_repo,
        ):
            with pytest.raises(ValueError) as exc_info:
                create_expense(input_)
        assert "Échec" in str(exc_info.value)


class TestUpdateExpenseStatus:
    """Commande update_expense_status."""

    def test_update_expense_status_calls_repo_update_status(self):
        input_ = UpdateExpenseStatusInput(
            expense_id="exp-123",
            status="validated",
        )
        updated_row = {
            "id": "exp-123",
            "employee_id": "emp-001",
            "date": "2025-03-15",
            "amount": 50.0,
            "type": "Restaurant",
            "status": "validated",
        }
        mock_repo = MagicMock()
        mock_repo.update_status.return_value = updated_row

        with patch(
            "app.modules.expenses.application.commands.ExpenseRepository",
            return_value=mock_repo,
        ):
            result = update_expense_status(input_)

        mock_repo.update_status.assert_called_once_with("exp-123", "validated")
        assert result == updated_row
        assert result["status"] == "validated"

    def test_update_expense_status_rejected(self):
        input_ = UpdateExpenseStatusInput(expense_id="exp-456", status="rejected")
        updated_row = {"id": "exp-456", "status": "rejected"}
        mock_repo = MagicMock()
        mock_repo.update_status.return_value = updated_row

        with patch(
            "app.modules.expenses.application.commands.ExpenseRepository",
            return_value=mock_repo,
        ):
            result = update_expense_status(input_)

        mock_repo.update_status.assert_called_once_with("exp-456", "rejected")
        assert result["status"] == "rejected"

    def test_update_expense_status_not_found_returns_none(self):
        input_ = UpdateExpenseStatusInput(
            expense_id="exp-inexistant", status="validated"
        )
        mock_repo = MagicMock()
        mock_repo.update_status.return_value = None

        with patch(
            "app.modules.expenses.application.commands.ExpenseRepository",
            return_value=mock_repo,
        ):
            result = update_expense_status(input_)

        assert result is None
        mock_repo.update_status.assert_called_once_with("exp-inexistant", "validated")


class TestUpdateAndDeleteExpense:
    """Modification / suppression d'une note (RH)."""

    def _update(self, existing, **champs):
        from app.modules.expenses.application.commands import update_expense
        from app.modules.expenses.application.dto import UpdateExpenseInput

        mock_repo = MagicMock()
        mock_repo.get_by_id.return_value = existing
        mock_repo.update.side_effect = lambda _id, data: {**existing, **data}
        with patch(
            "app.modules.expenses.application.commands.ExpenseRepository",
            return_value=mock_repo,
        ):
            update_expense(UpdateExpenseInput(expense_id="exp-1", **champs))
        return mock_repo.update.call_args[0][1]

    def test_modification_du_montant_recalcule_ht_et_tva(self):
        existing = {"id": "exp-1", "amount": 55.0, "vat_rate": 10.0, "type": "Restaurant"}
        payload = self._update(existing, amount=110.0)
        assert payload["amount"] == 110.0
        assert payload["amount_ht"] == 100.0
        assert payload["vat_amount"] == 10.0

    def test_bascule_vers_ik_force_la_tva_a_zero(self):
        existing = {"id": "exp-1", "amount": 120.0, "vat_rate": 10.0, "type": "Transport"}
        payload = self._update(existing, type="Indemnités kilométriques")
        assert payload["vat_rate"] == 0.0
        assert payload["amount_ht"] == 120.0
        assert payload["vat_amount"] == 0.0

    def test_note_inconnue_renvoie_none(self):
        from app.modules.expenses.application.commands import update_expense
        from app.modules.expenses.application.dto import UpdateExpenseInput

        mock_repo = MagicMock()
        mock_repo.get_by_id.return_value = None
        with patch(
            "app.modules.expenses.application.commands.ExpenseRepository",
            return_value=mock_repo,
        ):
            assert update_expense(UpdateExpenseInput(expense_id="exp-x")) is None
        mock_repo.update.assert_not_called()

    def test_suppression_renvoie_le_resultat_du_repo(self):
        from app.modules.expenses.application.commands import delete_expense

        mock_repo = MagicMock()
        mock_repo.delete.return_value = True
        with patch(
            "app.modules.expenses.application.commands.ExpenseRepository",
            return_value=mock_repo,
        ):
            assert delete_expense("exp-1") is True
        mock_repo.delete.assert_called_once_with("exp-1")

    def test_patch_description_seule_ne_touche_pas_aux_montants(self):
        """Un PATCH partiel reste partiel : sans montant ni taux, les colonnes
        monétaires ne sont pas réécrites (une TVA inconnue reste inconnue)."""
        from app.modules.expenses.application.commands import update_expense
        from app.modules.expenses.application.dto import UpdateExpenseInput

        existing = {"id": "exp-1", "amount": 120.0, "vat_rate": None, "type": "Autre"}
        mock_repo = MagicMock()
        mock_repo.get_by_id.return_value = existing
        mock_repo.update.side_effect = lambda _id, data: {**existing, **data}
        with patch(
            "app.modules.expenses.application.commands.ExpenseRepository",
            return_value=mock_repo,
        ):
            update_expense(
                UpdateExpenseInput(
                    expense_id="exp-1",
                    description="Repas client",
                    description_definie=True,
                )
            )
        payload = mock_repo.update.call_args[0][1]
        assert payload == {"description": "Repas client"}

    def test_montant_modifie_avec_taux_inconnu_ne_l_invente_pas(self):
        from app.modules.expenses.application.commands import update_expense
        from app.modules.expenses.application.dto import UpdateExpenseInput

        existing = {"id": "exp-1", "amount": 120.0, "vat_rate": None, "type": "Autre"}
        mock_repo = MagicMock()
        mock_repo.get_by_id.return_value = existing
        mock_repo.update.side_effect = lambda _id, data: {**existing, **data}
        with patch(
            "app.modules.expenses.application.commands.ExpenseRepository",
            return_value=mock_repo,
        ):
            update_expense(UpdateExpenseInput(expense_id="exp-1", amount=200.0))
        payload = mock_repo.update.call_args[0][1]
        assert payload["amount"] == 200.0
        assert payload["amount_ht"] is None
        assert payload["vat_amount"] is None
        assert "vat_rate" not in payload

    def test_quitter_un_type_exonere_sans_taux_est_refuse(self):
        from app.modules.expenses.application.commands import update_expense
        from app.modules.expenses.application.dto import UpdateExpenseInput

        existing = {
            "id": "exp-1",
            "amount": 120.0,
            "vat_rate": 0.0,
            "type": "Indemnités kilométriques",
        }
        mock_repo = MagicMock()
        mock_repo.get_by_id.return_value = existing
        with patch(
            "app.modules.expenses.application.commands.ExpenseRepository",
            return_value=mock_repo,
        ):
            with pytest.raises(ValueError, match="taux de TVA"):
                update_expense(
                    UpdateExpenseInput(expense_id="exp-1", type="Transport")
                )
        mock_repo.update.assert_not_called()

    def test_suppression_purge_le_justificatif(self):
        from app.modules.expenses.application.commands import delete_expense

        existing = {
            "id": "exp-1",
            "company_id": "comp-1",
            "receipt_url": "emp-1/facture.pdf",
        }
        mock_repo = MagicMock()
        mock_repo.get_by_id.return_value = existing
        mock_repo.delete.return_value = True
        mock_storage = MagicMock()
        with patch(
            "app.modules.expenses.application.commands.ExpenseRepository",
            return_value=mock_repo,
        ):
            with patch(
                "app.modules.expenses.infrastructure.providers.ExpenseStorageProvider",
                return_value=mock_storage,
            ):
                assert delete_expense("exp-1", company_id="comp-1") is True
        mock_storage.remove.assert_called_once_with(["emp-1/facture.pdf"])

    def test_suppression_refusee_hors_societe(self):
        from app.modules.expenses.application.commands import delete_expense

        mock_repo = MagicMock()
        mock_repo.get_by_id.return_value = {"id": "exp-1", "company_id": "comp-AUTRE"}
        with patch(
            "app.modules.expenses.application.commands.ExpenseRepository",
            return_value=mock_repo,
        ):
            assert delete_expense("exp-1", company_id="comp-1") is False
        mock_repo.delete.assert_not_called()
