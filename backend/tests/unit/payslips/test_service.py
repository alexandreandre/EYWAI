"""
Tests unitaires du service applicatif payslips (application/service.py).

Dépendances mockées : commands, queries, readers (payslip_meta_reader, debug_storage_info_provider).
"""

from unittest.mock import MagicMock, patch

import pytest

from app.modules.payslips.application.dto import (
    UserContext,
    PayslipNotFoundError,
    PayslipForbiddenError,
    PayslipBadRequestError,
)
from app.modules.payslips.application.service import (
    generate_payslip_use_case,
    delete_payslip_use_case,
    get_debug_storage_info,
    get_payslip_details_for_user,
    get_payslip_history_for_user,
    edit_payslip_for_user,
    restore_payslip_for_user,
    edit_payslip_use_case,
    restore_payslip_use_case,
)


def _ctx_employee(employee_id: str):
    """Contexte utilisateur = employé (pas RH, pas super admin)."""
    return UserContext(
        user_id=employee_id,
        is_super_admin=False,
        has_rh_access_in_company=lambda c: False,
        active_company_id="co-1",
        first_name="Jean",
        last_name="Dupont",
    )


def _ctx_rh(company_id: str):
    """Contexte utilisateur RH sur une entreprise."""
    return UserContext(
        user_id="rh-user",
        is_super_admin=False,
        has_rh_access_in_company=lambda c: c == company_id,
        active_company_id=company_id,
        first_name="RH",
        last_name="Test",
    )


def _ctx_super_admin():
    """Contexte super admin."""
    return UserContext(
        user_id="super-admin",
        is_super_admin=True,
        has_rh_access_in_company=lambda c: True,
        active_company_id=None,
        first_name="Admin",
        last_name="Super",
    )


class TestGeneratePayslipUseCase:
    """Tests de generate_payslip_use_case."""

    def test_returns_result_from_generate_payslip_command(self):
        """Délègue à generate_payslip et retourne le résultat."""
        with patch(
            "app.modules.payslips.application.service.generate_payslip"
        ) as mock_cmd:
            mock_cmd.return_value = MagicMock(
                status="ok", message="OK", download_url="https://u.fr"
            )
            result = generate_payslip_use_case("emp-1", 2024, 3)
        mock_cmd.assert_called_once()
        call_arg = mock_cmd.call_args[0][0]
        assert call_arg.employee_id == "emp-1"
        assert call_arg.year == 2024
        assert call_arg.month == 3
        assert result.status == "ok"
        assert result.download_url == "https://u.fr"


class TestDeletePayslipUseCase:
    """Tests de delete_payslip_use_case."""

    def test_calls_command_delete(self):
        """Appelle la commande delete_payslip."""
        with patch(
            "app.modules.payslips.application.service.cmd_delete_payslip"
        ) as mock_cmd:
            delete_payslip_use_case("ps-1")
            mock_cmd.assert_called_once_with("ps-1")


class TestGetDebugStorageInfo:
    """Tests de get_debug_storage_info."""

    def test_returns_info_from_provider(self):
        """Retourne les métadonnées storage du provider."""
        expected = {"path": "co/emp/bulletins/Bulletin_03-2024.pdf", "size": 12345}
        with patch(
            "app.modules.payslips.application.service.debug_storage_info_provider"
        ) as mock_provider:
            mock_provider.get_debug_storage_info.return_value = expected
            result = get_debug_storage_info("emp-1", 2024, 3)
        mock_provider.get_debug_storage_info.assert_called_once_with("emp-1", 2024, 3)
        assert result == expected

    def test_raises_payslip_not_found_when_employee_not_found(self):
        """Lève PayslipNotFoundError si le provider lève ValueError 'Employé non trouvé'."""
        with patch(
            "app.modules.payslips.application.service.debug_storage_info_provider"
        ) as mock_provider:
            mock_provider.get_debug_storage_info.side_effect = ValueError(
                "Employé non trouvé."
            )
            with pytest.raises(PayslipNotFoundError) as exc_info:
                get_debug_storage_info("emp-unknown", 2024, 1)
            assert "Employé non trouvé" in str(exc_info.value)

    def test_reraises_other_value_error(self):
        """Propage les autres ValueError du provider."""
        with patch(
            "app.modules.payslips.application.service.debug_storage_info_provider"
        ) as mock_provider:
            mock_provider.get_debug_storage_info.side_effect = ValueError(
                "Autre erreur"
            )
            with pytest.raises(ValueError):
                get_debug_storage_info("emp-1", 2024, 1)


class TestGetPayslipDetailsForUser:
    """Tests de get_payslip_details_for_user (avec autorisation)."""

    def test_returns_detail_when_employee_views_own(self):
        """L'employé peut voir son propre bulletin."""
        detail = {
            "id": "ps-1",
            "employee_id": "emp-1",
            "company_id": "co-1",
            "url": "https://u.fr",
        }
        ctx = _ctx_employee("emp-1")
        with patch(
            "app.modules.payslips.application.service.get_payslip_details",
            return_value=detail,
        ):
            result = get_payslip_details_for_user("ps-1", ctx)
        assert result == detail

    def test_raises_not_found_when_detail_is_none(self):
        """Lève PayslipNotFoundError si le bulletin n'existe pas."""
        ctx = _ctx_employee("emp-1")
        with patch(
            "app.modules.payslips.application.service.get_payslip_details",
            return_value=None,
        ):
            with pytest.raises(PayslipNotFoundError):
                get_payslip_details_for_user("ps-unknown", ctx)

    def test_raises_forbidden_when_user_cannot_view(self):
        """Lève PayslipForbiddenError si l'utilisateur n'a pas le droit (pas employé, pas RH, pas super admin)."""
        detail = {"id": "ps-1", "employee_id": "emp-1", "company_id": "co-1"}
        ctx = _ctx_employee("other-user")  # autre utilisateur, pas RH
        with patch(
            "app.modules.payslips.application.service.get_payslip_details",
            return_value=detail,
        ):
            with pytest.raises(PayslipForbiddenError):
                get_payslip_details_for_user("ps-1", ctx)

    def test_rh_with_access_can_view(self):
        """Un RH avec accès à l'entreprise du bulletin peut consulter."""
        detail = {"id": "ps-1", "employee_id": "emp-1", "company_id": "co-1"}
        ctx = _ctx_rh("co-1")
        with patch(
            "app.modules.payslips.application.service.get_payslip_details",
            return_value=detail,
        ):
            result = get_payslip_details_for_user("ps-1", ctx)
        assert result == detail

    def test_super_admin_can_view_any(self):
        """Un super admin peut consulter n'importe quel bulletin."""
        detail = {"id": "ps-1", "employee_id": "emp-1", "company_id": "co-1"}
        ctx = _ctx_super_admin()
        with patch(
            "app.modules.payslips.application.service.get_payslip_details",
            return_value=detail,
        ):
            result = get_payslip_details_for_user("ps-1", ctx)
        assert result == detail


class TestGetPayslipHistoryForUser:
    """Tests de get_payslip_history_for_user."""

    def test_returns_history_when_meta_found_and_user_can_view(self):
        """Retourne l'historique si la meta existe et l'utilisateur a le droit."""
        meta = {"employee_id": "emp-1", "company_id": "co-1"}
        history = [{"version": 1, "edited_by": "user-1"}]
        ctx = _ctx_employee("emp-1")
        with (
            patch(
                "app.modules.payslips.application.service.payslip_meta_reader"
            ) as mock_reader,
            patch(
                "app.modules.payslips.application.service.get_payslip_history",
                return_value=history,
            ),
        ):
            mock_reader.get_payslip_meta.return_value = meta
            result = get_payslip_history_for_user("ps-1", ctx)
        assert result == history

    def test_raises_not_found_when_meta_is_none(self):
        """Lève PayslipNotFoundError si le bulletin n'existe pas (meta None)."""
        ctx = _ctx_employee("emp-1")
        with patch(
            "app.modules.payslips.application.service.payslip_meta_reader"
        ) as mock_reader:
            mock_reader.get_payslip_meta.return_value = None
            with pytest.raises(PayslipNotFoundError):
                get_payslip_history_for_user("ps-unknown", ctx)

    def test_raises_forbidden_when_user_cannot_view(self):
        """Lève PayslipForbiddenError si l'utilisateur n'a pas le droit."""
        meta = {"employee_id": "emp-1", "company_id": "co-1"}
        ctx = _ctx_employee("other-user")
        with patch(
            "app.modules.payslips.application.service.payslip_meta_reader"
        ) as mock_reader:
            mock_reader.get_payslip_meta.return_value = meta
            with pytest.raises(PayslipForbiddenError):
                get_payslip_history_for_user("ps-1", ctx)


class TestEditPayslipForUser:
    """Tests de edit_payslip_for_user."""

    def test_returns_result_when_rh_edits(self):
        """Un RH avec droit d'édition peut modifier et reçoit le résultat."""
        meta = {"employee_id": "emp-1", "company_id": "co-1"}
        ctx = _ctx_rh("co-1")
        expected = {"payslip": {"id": "ps-1"}, "new_pdf_url": "https://new.pdf"}
        with (
            patch(
                "app.modules.payslips.application.service.payslip_meta_reader"
            ) as mock_reader,
            patch(
                "app.modules.payslips.application.service.edit_payslip",
                return_value=expected,
            ),
        ):
            mock_reader.get_payslip_meta.return_value = meta
            result = edit_payslip_for_user(
                "ps-1", {"salaire_brut": 3000}, "Modif brut", ctx
            )
        assert result == expected

    def test_raises_not_found_when_meta_is_none(self):
        """Lève PayslipNotFoundError si bulletin inexistant."""
        ctx = _ctx_rh("co-1")
        with patch(
            "app.modules.payslips.application.service.payslip_meta_reader"
        ) as mock_reader:
            mock_reader.get_payslip_meta.return_value = None
            with pytest.raises(PayslipNotFoundError):
                edit_payslip_for_user("ps-unknown", {}, "Résumé", ctx)

    def test_raises_bad_request_when_no_company_id(self):
        """Lève PayslipBadRequestError si le bulletin n'a pas de company_id."""
        meta = {"employee_id": "emp-1", "company_id": None}
        ctx = _ctx_rh("co-1")
        with patch(
            "app.modules.payslips.application.service.payslip_meta_reader"
        ) as mock_reader:
            mock_reader.get_payslip_meta.return_value = meta
            with pytest.raises(PayslipBadRequestError):
                edit_payslip_for_user("ps-1", {}, "Résumé", ctx)

    def test_raises_forbidden_when_user_cannot_edit(self):
        """Lève PayslipForbiddenError si l'utilisateur n'a pas le droit d'éditer."""
        meta = {"employee_id": "emp-1", "company_id": "co-1"}
        ctx = _ctx_employee("emp-1")  # employé (pas RH) ne peut pas éditer
        with patch(
            "app.modules.payslips.application.service.payslip_meta_reader"
        ) as mock_reader:
            mock_reader.get_payslip_meta.return_value = meta
            with pytest.raises(PayslipForbiddenError):
                edit_payslip_for_user("ps-1", {}, "Résumé", ctx)


class TestRestorePayslipForUser:
    """Tests de restore_payslip_for_user."""

    def test_returns_result_when_rh_restores(self):
        """Un RH peut restaurer une version et reçoit le résultat."""
        meta = {"employee_id": "emp-1", "company_id": "co-1"}
        ctx = _ctx_rh("co-1")
        expected = {"payslip": {"id": "ps-1"}, "restored_version": 2}
        with (
            patch(
                "app.modules.payslips.application.service.payslip_meta_reader"
            ) as mock_reader,
            patch(
                "app.modules.payslips.application.service.restore_payslip_version",
                return_value=expected,
            ),
        ):
            mock_reader.get_payslip_meta.return_value = meta
            result = restore_payslip_for_user("ps-1", 2, ctx)
        assert result == expected

    def test_raises_not_found_when_meta_is_none(self):
        """Lève PayslipNotFoundError si bulletin inexistant."""
        ctx = _ctx_rh("co-1")
        with patch(
            "app.modules.payslips.application.service.payslip_meta_reader"
        ) as mock_reader:
            mock_reader.get_payslip_meta.return_value = None
            with pytest.raises(PayslipNotFoundError):
                restore_payslip_for_user("ps-unknown", 1, ctx)

    def test_raises_forbidden_when_user_cannot_restore(self):
        """Lève PayslipForbiddenError si l'utilisateur n'a pas le droit."""
        meta = {"employee_id": "emp-1", "company_id": "co-1"}
        ctx = _ctx_employee("emp-1")
        with patch(
            "app.modules.payslips.application.service.payslip_meta_reader"
        ) as mock_reader:
            mock_reader.get_payslip_meta.return_value = meta
            with pytest.raises(PayslipForbiddenError):
                restore_payslip_for_user("ps-1", 1, ctx)


class TestEditPayslipUseCaseLegacy:
    """Tests de edit_payslip_use_case (signature legacy user_id, user_name)."""

    def test_calls_edit_payslip_with_correct_input(self):
        """edit_payslip_use_case construit EditPayslipInput et appelle edit_payslip."""
        with patch(
            "app.modules.payslips.application.service.edit_payslip"
        ) as mock_edit:
            mock_edit.return_value = {"payslip": {}, "new_pdf_url": ""}
            edit_payslip_use_case(
                "ps-1",
                {"brut": 3000},
                "Résumé",
                "user-1",
                "Jean Dupont",
                pdf_notes="Note",
                internal_note="Interne",
            )
        call_arg = mock_edit.call_args[0][0]
        assert call_arg.payslip_id == "ps-1"
        assert call_arg.payslip_data == {"brut": 3000}
        assert call_arg.changes_summary == "Résumé"
        assert call_arg.current_user_id == "user-1"
        assert call_arg.current_user_name == "Jean Dupont"
        assert call_arg.pdf_notes == "Note"
        assert call_arg.internal_note == "Interne"


class TestRestorePayslipUseCaseLegacy:
    """Tests de restore_payslip_use_case (signature legacy)."""

    def test_calls_restore_payslip_version_with_correct_input(self):
        """restore_payslip_use_case construit RestorePayslipInput et appelle restore_payslip_version."""
        with patch(
            "app.modules.payslips.application.service.restore_payslip_version"
        ) as mock_restore:
            mock_restore.return_value = {}
            restore_payslip_use_case("ps-1", 2, "user-1", "Admin")
        call_arg = mock_restore.call_args[0][0]
        assert call_arg.payslip_id == "ps-1"
        assert call_arg.version == 2
        assert call_arg.current_user_id == "user-1"
        assert call_arg.current_user_name == "Admin"
