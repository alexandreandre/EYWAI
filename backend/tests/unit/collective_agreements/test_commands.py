"""
Tests des commandes applicatives collective_agreements.

Chaque commande est testée avec un service mocké ; on vérifie que la commande
délègue au service et retourne le résultat attendu.
"""

from unittest.mock import MagicMock


from app.modules.collective_agreements.application.commands import (
    create_catalog_item,
    update_catalog_item,
    delete_catalog_item,
    assign_agreement_to_company,
    unassign_agreement_from_company,
    refresh_text_cache,
)
from app.modules.collective_agreements.application.dto import CatalogCreateInput
from app.modules.collective_agreements.application.service import (
    CollectiveAgreementsService,
)


# --- create_catalog_item ---


class TestCreateCatalogItem:
    """Commande create_catalog_item."""

    def test_returns_service_result(self):
        data = CatalogCreateInput(
            name="CC Test",
            idcc="1486",
            description=None,
            sector="IT",
            effective_date=None,
            is_active=True,
            rules_pdf_path=None,
            rules_pdf_filename=None,
        )
        expected = {"id": "new-id", "name": "CC Test", "idcc": "1486"}
        mock_svc = MagicMock(spec=CollectiveAgreementsService)
        mock_svc.create_catalog_item.return_value = expected

        result = create_catalog_item(data, is_super_admin=True, service=mock_svc)

        assert result == expected
        mock_svc.create_catalog_item.assert_called_once_with(data, True)

    def test_passes_is_super_admin_false(self):
        data = CatalogCreateInput(
            name="CC",
            idcc="1234",
            description=None,
            sector=None,
            effective_date=None,
            is_active=True,
            rules_pdf_path=None,
            rules_pdf_filename=None,
        )
        mock_svc = MagicMock(spec=CollectiveAgreementsService)
        create_catalog_item(data, is_super_admin=False, service=mock_svc)
        mock_svc.create_catalog_item.assert_called_once_with(data, False)


# --- update_catalog_item ---


class TestUpdateCatalogItem:
    """Commande update_catalog_item."""

    def test_returns_updated_item(self):
        update_dict = {"name": "Nouveau nom", "description": "Nouvelle description"}
        expected = {"id": "agr-1", "name": "Nouveau nom"}
        mock_svc = MagicMock(spec=CollectiveAgreementsService)
        mock_svc.update_catalog_item.return_value = expected

        result = update_catalog_item(
            "agr-1", update_dict, is_super_admin=True, service=mock_svc
        )

        assert result == expected
        mock_svc.update_catalog_item.assert_called_once_with("agr-1", update_dict, True)

    def test_returns_none_when_service_returns_none(self):
        mock_svc = MagicMock(spec=CollectiveAgreementsService)
        mock_svc.update_catalog_item.return_value = None

        result = update_catalog_item(
            "agr-unknown", {"name": "X"}, is_super_admin=True, service=mock_svc
        )

        assert result is None


# --- delete_catalog_item ---


class TestDeleteCatalogItem:
    """Commande delete_catalog_item."""

    def test_returns_true_when_success(self):
        mock_svc = MagicMock(spec=CollectiveAgreementsService)
        mock_svc.delete_catalog_item.return_value = True

        result = delete_catalog_item("agr-1", is_super_admin=True, service=mock_svc)

        assert result is True
        mock_svc.delete_catalog_item.assert_called_once_with("agr-1", True)


# --- assign_agreement_to_company ---


class TestAssignAgreementToCompany:
    """Commande assign_agreement_to_company."""

    def test_returns_assignment_from_service(self):
        mock_svc = MagicMock(spec=CollectiveAgreementsService)
        expected = {
            "id": "assign-1",
            "company_id": "c1",
            "collective_agreement_id": "agr-1",
        }
        mock_svc.assign_to_company.return_value = expected

        result = assign_agreement_to_company(
            company_id="c1",
            collective_agreement_id="agr-1",
            user_id="user-1",
            has_rh_access=True,
            service=mock_svc,
        )

        assert result == expected
        mock_svc.assign_to_company.assert_called_once_with(
            "c1", "agr-1", "user-1", True
        )


# --- unassign_agreement_from_company ---


class TestUnassignAgreementFromCompany:
    """Commande unassign_agreement_from_company."""

    def test_returns_true_on_success(self):
        mock_svc = MagicMock(spec=CollectiveAgreementsService)
        mock_svc.unassign_from_company.return_value = True

        result = unassign_agreement_from_company(
            assignment_id="assign-1",
            company_id="c1",
            has_rh_access=True,
            service=mock_svc,
        )

        assert result is True
        mock_svc.unassign_from_company.assert_called_once_with("assign-1", "c1", True)


# --- refresh_text_cache ---


class TestRefreshTextCache:
    """Commande refresh_text_cache."""

    def test_calls_service_returns_none(self):
        mock_svc = MagicMock(spec=CollectiveAgreementsService)
        mock_svc.refresh_text_cache.return_value = None

        result = refresh_text_cache(
            agreement_id="agr-1", is_super_admin=True, service=mock_svc
        )

        assert result is None
        mock_svc.refresh_text_cache.assert_called_once_with("agr-1", True)
