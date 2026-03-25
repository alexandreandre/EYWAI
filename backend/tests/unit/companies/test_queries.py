"""
Tests unitaires des queries du module companies (application/queries.py).

Repositories et providers mockés : pas d'accès DB.
"""

from unittest.mock import MagicMock, patch

import pytest

from app.modules.companies.application import queries
from app.modules.companies.application.dto import (
    CompanyDetailsWithKpisDto,
    CompanySettingsResultDto,
)


MODULE_QUERIES = "app.modules.companies.application.queries"


class TestGetCompanyDetailsAndKpis:
    """Query get_company_details_and_kpis."""

    def test_returns_dto_with_company_data_and_kpis(self):
        """Retourne CompanyDetailsWithKpisDto avec company_data et kpis calculés."""
        company_data = {"id": "c1", "company_name": "Test SARL"}
        employees = [{"id": "e1", "contract_type": "CDI", "job_title": "Dev"}]
        payslips = []

        with patch(
            f"{MODULE_QUERIES}.fetch_company_with_employees_and_payslips",
            return_value={
                "company_data": company_data,
                "employees": employees,
                "payslips": payslips,
            },
        ):
            result = queries.get_company_details_and_kpis(
                company_id="c1",
                current_user=MagicMock(),
            )

        assert isinstance(result, CompanyDetailsWithKpisDto)
        assert result.company_data == company_data
        assert result.kpis["total_employees"] == 1
        assert "last_month_gross_salary" in result.kpis
        assert "evolution_12_months" in result.kpis
        assert "contract_distribution" in result.kpis

    def test_raises_lookup_error_when_company_data_missing(self):
        """LookupError si company_data est None (entreprise non trouvée)."""
        with patch(
            f"{MODULE_QUERIES}.fetch_company_with_employees_and_payslips",
            return_value={"company_data": None, "employees": [], "payslips": []},
        ):
            with pytest.raises(
                LookupError, match="Données de l'entreprise non trouvées"
            ):
                queries.get_company_details_and_kpis(
                    company_id="unknown",
                    current_user=MagicMock(),
                )


class TestGetCompanySettings:
    """Query get_company_settings."""

    def test_returns_dto_when_settings_found(self):
        """Retourne CompanySettingsResultDto avec medical_follow_up_enabled et settings."""
        mock_repo = MagicMock()
        mock_repo.get_settings.return_value = {
            "medical_follow_up_enabled": True,
            "custom_key": "value",
        }

        with patch(f"{MODULE_QUERIES}.company_repository", mock_repo):
            result = queries.get_company_settings(
                company_id="company-1",
                current_user=MagicMock(),
            )

        assert isinstance(result, CompanySettingsResultDto)
        assert result.medical_follow_up_enabled is True
        assert result.settings == {
            "medical_follow_up_enabled": True,
            "custom_key": "value",
        }
        mock_repo.get_settings.assert_called_once_with("company-1")

    def test_raises_lookup_error_when_company_not_found(self):
        """LookupError si get_settings retourne None."""
        mock_repo = MagicMock()
        mock_repo.get_settings.return_value = None

        with patch(f"{MODULE_QUERIES}.company_repository", mock_repo):
            with pytest.raises(LookupError, match="Entreprise non trouvée"):
                queries.get_company_settings(
                    company_id="unknown",
                    current_user=MagicMock(),
                )

    def test_medical_follow_up_false_when_absent(self):
        """medical_follow_up_enabled False quand clé absente des settings."""
        mock_repo = MagicMock()
        mock_repo.get_settings.return_value = {}

        with patch(f"{MODULE_QUERIES}.company_repository", mock_repo):
            result = queries.get_company_settings(
                company_id="company-2",
                current_user=MagicMock(),
            )
        assert result.medical_follow_up_enabled is False
        assert result.settings == {}
