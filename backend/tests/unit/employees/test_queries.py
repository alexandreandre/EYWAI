"""
Tests unitaires des queries du module employees.

Repository et providers mockés. Pas d'accès DB ni HTTP.
"""

from unittest.mock import MagicMock, patch

import pytest

from app.modules.employees.application import queries as queries_module


pytestmark = pytest.mark.unit


@patch(
    "app.modules.employees.application.queries.enrich_employee_with_residence_permit_status"
)
@patch("app.modules.employees.application.queries._employee_repository")
def test_get_employees_returns_enriched_list(mock_repo, mock_enrich):
    """get_employees : retourne la liste enrichie avec statut titre de séjour."""
    mock_repo.get_by_company.return_value = [
        {"id": "e1", "first_name": "Jean", "last_name": "Dupont", "company_id": "c1"},
    ]
    mock_enrich.side_effect = lambda row: {**row, "residence_permit_status": "valid"}
    result = queries_module.get_employees("company-1")
    mock_repo.get_by_company.assert_called_once_with("company-1")
    assert len(result) == 1
    assert result[0]["residence_permit_status"] == "valid"


@patch("app.modules.employees.application.queries.enrich_employee_with_annual_review")
@patch(
    "app.modules.employees.application.queries.enrich_employee_with_residence_permit_status"
)
@patch("app.modules.employees.application.queries._employee_repository")
def test_get_employee_by_id_returns_enriched_employee(
    mock_repo, mock_enrich_res, mock_enrich_review
):
    """get_employee_by_id : retourne l'employé enrichi titre de séjour + entretien annuel."""
    raw = {"id": "e1", "first_name": "Jean", "company_id": "c1"}
    mock_repo.get_by_id.return_value = raw
    mock_enrich_res.side_effect = lambda d: {**d, "residence_permit_status": "valid"}
    mock_enrich_review.side_effect = lambda d: {**d, "annual_review_current_year": 2025}
    result = queries_module.get_employee_by_id("e1", "c1")
    mock_repo.get_by_id.assert_called_once_with("e1", "c1")
    assert result is not None
    assert result["residence_permit_status"] == "valid"
    assert result["annual_review_current_year"] == 2025


@patch("app.modules.employees.application.queries.enrich_employee_with_annual_review")
@patch(
    "app.modules.employees.application.queries.enrich_employee_with_residence_permit_status"
)
@patch("app.modules.employees.application.queries._employee_repository")
def test_get_employee_by_id_not_found_returns_none(
    mock_repo, mock_enrich_res, mock_enrich_review
):
    """get_employee_by_id : si employé inexistant → None."""
    mock_repo.get_by_id.return_value = None
    result = queries_module.get_employee_by_id("unknown", "c1")
    assert result is None
    mock_enrich_res.assert_not_called()
    mock_enrich_review.assert_not_called()


@patch("app.modules.employees.application.queries.get_storage_provider")
@patch("app.modules.employees.application.queries.get_employee_company_id")
def test_get_my_contract_url_no_company_returns_none(mock_get_company, mock_storage):
    """get_my_contract_url : pas de company_id pour l'employé → None."""
    mock_get_company.return_value = None
    result = queries_module.get_my_contract_url("emp-1")
    assert result is None
    mock_storage.assert_not_called()


@patch("app.modules.employees.application.queries.get_storage_provider")
@patch("app.modules.employees.application.queries.get_employee_company_id")
def test_get_my_contract_url_no_contract_file_returns_none(
    mock_get_company, mock_storage
):
    """get_my_contract_url : pas de fichier contrat.pdf → None."""
    mock_get_company.return_value = "c1"
    storage = MagicMock()
    storage.list_files.return_value = []  # pas de contrat.pdf
    mock_storage.return_value = storage
    result = queries_module.get_my_contract_url("emp-1")
    assert result is None


@patch("app.modules.employees.application.queries.get_storage_provider")
@patch("app.modules.employees.application.queries.get_employee_company_id")
def test_get_my_contract_url_returns_signed_url(mock_get_company, mock_storage):
    """get_my_contract_url : contrat présent → URL signée."""
    mock_get_company.return_value = "c1"
    storage = MagicMock()
    storage.list_files.return_value = [{"name": "contrat.pdf"}]
    storage.create_signed_url.return_value = "https://signed.url/contrat.pdf"
    mock_storage.return_value = storage
    result = queries_module.get_my_contract_url("emp-1")
    assert result == "https://signed.url/contrat.pdf"
    storage.create_signed_url.assert_called_once()
    call_kw = storage.create_signed_url.call_args[1]
    assert call_kw.get("expiry_seconds") == 3600
    assert "contrat.pdf" in str(storage.create_signed_url.call_args[0])


@patch("app.modules.employees.application.queries.get_employee_company_id")
@patch("app.modules.employees.application.queries.fetch_published_exit_documents")
def test_get_my_published_exit_documents_no_company_returns_empty(
    mock_fetch, mock_get_company
):
    """get_my_published_exit_documents : pas de company_id → liste vide."""
    mock_get_company.return_value = None
    result = queries_module.get_my_published_exit_documents("emp-1")
    assert result == []
    mock_fetch.assert_not_called()


@patch("app.modules.employees.application.queries.get_employee_company_id")
@patch("app.modules.employees.application.queries.fetch_published_exit_documents")
def test_get_my_published_exit_documents_returns_docs(mock_fetch, mock_get_company):
    """get_my_published_exit_documents : retourne la liste des documents de sortie."""
    mock_get_company.return_value = "c1"
    mock_fetch.return_value = [
        {"id": "doc1", "name": "Attestation", "url": "https://u"}
    ]
    result = queries_module.get_my_published_exit_documents("emp-1")
    assert len(result) == 1
    assert result[0]["name"] == "Attestation"
    mock_fetch.assert_called_once_with("emp-1", "c1")


@patch("app.modules.employees.application.queries.provider_get_promotions")
def test_get_employee_promotions_delegates_to_provider(mock_get_promotions):
    """get_employee_promotions : délègue au provider promotions."""
    mock_get_promotions.return_value = [
        {"id": "p1", "promotion_type": "salaire", "effective_date": "2025-01-01"},
    ]
    result = queries_module.get_employee_promotions("c1", "emp-1")
    mock_get_promotions.assert_called_once_with(company_id="c1", employee_id="emp-1")
    assert len(result) == 1
    assert result[0]["promotion_type"] == "salaire"


@patch("app.modules.employees.application.queries.get_company_id_for_user_from_profile")
def test_get_company_id_for_creator_returns_profile_company(mock_get_profile):
    """get_company_id_for_creator : retourne le company_id du profil utilisateur."""
    mock_get_profile.return_value = "company-abc"
    result = queries_module.get_company_id_for_creator("user-1")
    assert result == "company-abc"
    mock_get_profile.assert_called_once_with("user-1")


@patch("app.modules.employees.application.queries.provider_get_employee_rh_access")
def test_get_employee_rh_access_delegates_to_provider(mock_get_rh):
    """get_employee_rh_access : délègue au provider et retourne has_access, roles."""
    mock_get_rh.return_value = {
        "has_access": True,
        "current_role": "rh",
        "can_grant_access": True,
        "available_roles": ["collaborateur_rh", "rh", "admin"],
    }
    result = queries_module.get_employee_rh_access("emp-1", "c1")
    mock_get_rh.assert_called_once_with(employee_id="emp-1", company_id="c1")
    assert result["has_access"] is True
    assert result["current_role"] == "rh"
