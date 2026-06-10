"""
Tests unitaires des commandes du module payslips (application/commands.py).

Chaque commande est testée avec repositories et providers mockés (pas de DB, pas de HTTP).
"""

from unittest.mock import patch

import pytest

from app.modules.payslips.application.commands import (
    generate_payslip,
    delete_payslip,
    edit_payslip,
    restore_payslip_version,
)
from app.modules.payslips.application.dto import (
    GeneratePayslipInput,
    EditPayslipInput,
    RestorePayslipInput,
    PayslipBadRequestError,
)

_COMPLETE_EMPLOYEE = {
    "id": "emp-1",
    "employment_status": "actif",
    "nir": "1850574001234",
    "date_naissance": "1985-05-01",
    "adresse": {"ville": "Paris"},
    "coordonnees_bancaires": {"iban": "FR7612345678901234567890123"},
    "salaire_de_base": {"montant": 2500},
}


class TestGeneratePayslipCommand:
    """Tests de la commande generate_payslip."""

    def test_raises_when_employee_onboarding_incomplete(self):
        cmd = GeneratePayslipInput(employee_id="emp-1", year=2024, month=3)
        with patch(
            "app.modules.payslips.application.commands._employee_repository"
        ) as mock_repo:
            mock_repo.get_by_id_only.return_value = {
                "id": "emp-1",
                "employment_status": "en_onboarding",
                "first_name": "Terence",
            }
            with pytest.raises(PayslipBadRequestError) as exc:
                generate_payslip(cmd)
        assert "onboarding" in str(exc.value).lower()

    def test_generates_forfait_when_statut_is_forfait_jour(self):
        """Quand le statut employé est forfait jour, délègue à generate_forfait."""
        cmd = GeneratePayslipInput(employee_id="emp-1", year=2024, month=3)
        mock_result = {
            "status": "ok",
            "message": "Généré",
            "download_url": "https://example.com/doc.pdf",
        }

        with (
            patch(
                "app.modules.payslips.application.commands.employee_statut_reader"
            ) as mock_reader,
            patch(
                "app.modules.payslips.application.commands.payslip_generator_provider"
            ) as mock_provider,
            patch(
                "app.modules.payslips.application.commands._employee_repository"
            ) as mock_repo,
        ):
            mock_repo.get_by_id_only.return_value = {
                **_COMPLETE_EMPLOYEE,
                "id": "emp-1",
            }
            mock_reader.get_employee_statut.return_value = "Cadre forfait jour"
            mock_provider.generate_forfait.return_value = mock_result
            mock_provider.generate_heures.return_value = {}

            result = generate_payslip(cmd)

        mock_reader.get_employee_statut.assert_called_once_with("emp-1")
        mock_provider.generate_forfait.assert_called_once_with(
            employee_id="emp-1", year=2024, month=3
        )
        mock_provider.generate_heures.assert_not_called()
        assert result.status == "ok"
        assert result.message == "Généré"
        assert result.download_url == "https://example.com/doc.pdf"

    def test_generates_heures_when_statut_is_not_forfait_jour(self):
        """Quand le statut n'est pas forfait jour, délègue à generate_heures."""
        cmd = GeneratePayslipInput(employee_id="emp-2", year=2024, month=6)
        mock_result = {
            "status": "ok",
            "message": "Bulletin heures",
            "download_url": "https://example.com/h.pdf",
        }

        with (
            patch(
                "app.modules.payslips.application.commands.employee_statut_reader"
            ) as mock_reader,
            patch(
                "app.modules.payslips.application.commands.payslip_generator_provider"
            ) as mock_provider,
            patch(
                "app.modules.payslips.application.commands._employee_repository"
            ) as mock_repo,
        ):
            mock_repo.get_by_id_only.return_value = {
                **_COMPLETE_EMPLOYEE,
                "id": "emp-2",
            }
            mock_reader.get_employee_statut.return_value = "Cadre au forfait heures"
            mock_provider.generate_heures.return_value = mock_result
            mock_provider.generate_forfait.return_value = {}

            result = generate_payslip(cmd)

        mock_reader.get_employee_statut.assert_called_once_with("emp-2")
        mock_provider.generate_heures.assert_called_once_with(
            employee_id="emp-2", year=2024, month=6
        )
        mock_provider.generate_forfait.assert_not_called()
        assert result.status == "ok"
        assert result.download_url == "https://example.com/h.pdf"

    def test_generates_heures_when_statut_is_none(self):
        """Quand le statut est None (employé sans statut), utilise generate_heures."""
        cmd = GeneratePayslipInput(employee_id="emp-3", year=2025, month=1)
        mock_result = {"status": "ok", "message": "OK", "download_url": ""}

        with (
            patch(
                "app.modules.payslips.application.commands.employee_statut_reader"
            ) as mock_reader,
            patch(
                "app.modules.payslips.application.commands.payslip_generator_provider"
            ) as mock_provider,
            patch(
                "app.modules.payslips.application.commands._employee_repository"
            ) as mock_repo,
        ):
            mock_repo.get_by_id_only.return_value = {
                **_COMPLETE_EMPLOYEE,
                "id": "emp-3",
            }
            mock_reader.get_employee_statut.return_value = None
            mock_provider.generate_heures.return_value = mock_result

            result = generate_payslip(cmd)

        mock_provider.generate_heures.assert_called_once()
        mock_provider.generate_forfait.assert_not_called()
        assert result.status == "ok"

    def test_notifies_employee_when_generation_succeeds(self):
        cmd = GeneratePayslipInput(employee_id="emp-1", year=2024, month=3)
        mock_result = {
            "status": "success",
            "message": "Bulletin généré avec succès.",
            "download_url": "https://example.com/doc.pdf",
            "payslip_id": "ps-1",
        }

        with (
            patch(
                "app.modules.payslips.application.commands.employee_statut_reader"
            ) as mock_reader,
            patch(
                "app.modules.payslips.application.commands.payslip_generator_provider"
            ) as mock_provider,
            patch(
                "app.modules.payslips.application.commands._employee_repository"
            ) as mock_repo,
            patch(
                "app.modules.payslips.application.commands.notify_employee_new_document"
            ) as mock_notify,
        ):
            mock_repo.get_by_id_only.return_value = {
                **_COMPLETE_EMPLOYEE,
                "id": "emp-1",
                "company_id": "co-1",
            }
            mock_reader.get_employee_statut.return_value = "Cadre au forfait heures"
            mock_provider.generate_heures.return_value = mock_result

            generate_payslip(cmd)

        mock_notify.assert_called_once_with(
            "emp-1",
            "co-1",
            "Bulletin de paie — mars 2024",
            page_path="payslips",
            notification_type="nouveau_bulletin",
        )

    def test_skips_notification_when_generation_fails(self):
        cmd = GeneratePayslipInput(employee_id="emp-1", year=2024, month=3)
        mock_result = {
            "status": "error",
            "message": "Échec",
            "download_url": "",
        }

        with (
            patch(
                "app.modules.payslips.application.commands.employee_statut_reader"
            ) as mock_reader,
            patch(
                "app.modules.payslips.application.commands.payslip_generator_provider"
            ) as mock_provider,
            patch(
                "app.modules.payslips.application.commands._employee_repository"
            ) as mock_repo,
            patch(
                "app.modules.payslips.application.commands.notify_employee_new_document"
            ) as mock_notify,
        ):
            mock_repo.get_by_id_only.return_value = {
                **_COMPLETE_EMPLOYEE,
                "id": "emp-1",
                "company_id": "co-1",
            }
            mock_reader.get_employee_statut.return_value = "Cadre au forfait heures"
            mock_provider.generate_heures.return_value = mock_result

            generate_payslip(cmd)

        mock_notify.assert_not_called()


class TestDeletePayslipCommand:
    """Tests de la commande delete_payslip."""

    def test_calls_repository_delete(self):
        """delete_payslip appelle le repository avec l'id du bulletin."""
        with patch(
            "app.modules.payslips.infrastructure.repository.payslip_repository"
        ) as mock_repo:
            delete_payslip("ps-123")
            mock_repo.delete.assert_called_once_with("ps-123")


class TestEditPayslipCommand:
    """Tests de la commande edit_payslip."""

    def test_delegates_to_editor_provider_save_edited(self):
        """edit_payslip délègue au provider save_edited avec les bons paramètres."""
        cmd = EditPayslipInput(
            payslip_id="ps-1",
            payslip_data={"salaire_brut": 3000},
            changes_summary="Modif brut",
            current_user_id="user-1",
            current_user_name="Jean Dupont",
            pdf_notes="Note PDF",
            internal_note="Note interne",
        )
        expected = {
            "payslip": {"id": "ps-1"},
            "new_pdf_url": "https://example.com/new.pdf",
        }

        with patch(
            "app.modules.payslips.application.commands.payslip_editor_provider"
        ) as mock_editor:
            mock_editor.save_edited.return_value = expected
            result = edit_payslip(cmd)

        mock_editor.save_edited.assert_called_once_with(
            payslip_id="ps-1",
            new_payslip_data={"salaire_brut": 3000},
            changes_summary="Modif brut",
            current_user_id="user-1",
            current_user_name="Jean Dupont",
            pdf_notes="Note PDF",
            internal_note="Note interne",
        )
        assert result == expected

    def test_edit_without_optional_notes(self):
        """edit_payslip peut être appelé sans pdf_notes ni internal_note."""
        cmd = EditPayslipInput(
            payslip_id="ps-2",
            payslip_data={},
            changes_summary="Résumé",
            current_user_id="user-2",
            current_user_name="Marie",
        )
        with patch(
            "app.modules.payslips.application.commands.payslip_editor_provider"
        ) as mock_editor:
            mock_editor.save_edited.return_value = {}
            edit_payslip(cmd)
        call_kw = mock_editor.save_edited.call_args[1]
        assert call_kw["pdf_notes"] is None
        assert call_kw["internal_note"] is None


class TestRestorePayslipVersionCommand:
    """Tests de la commande restore_payslip_version."""

    def test_delegates_to_editor_provider_restore_version(self):
        """restore_payslip_version délègue au provider restore_version."""
        cmd = RestorePayslipInput(
            payslip_id="ps-1",
            version=2,
            current_user_id="user-1",
            current_user_name="Admin",
        )
        expected = {"payslip": {"id": "ps-1"}, "restored_version": 2}

        with patch(
            "app.modules.payslips.application.commands.payslip_editor_provider"
        ) as mock_editor:
            mock_editor.restore_version.return_value = expected
            result = restore_payslip_version(cmd)

        mock_editor.restore_version.assert_called_once_with(
            payslip_id="ps-1",
            version=2,
            current_user_id="user-1",
            current_user_name="Admin",
        )
        assert result == expected
