"""Tests unitaires — résolution entreprise import CP."""

from unittest.mock import MagicMock, patch

from app.modules.admin_import.infrastructure.repository import (
    find_company_by_normalized_name,
    resolve_company_from_payslip,
)


MBC_COMPANY = {
    "id": "co-mbc",
    "company_name": "Mont Blanc Composite",
    "siret": None,
    "siren": None,
}


class TestFindCompanyByNormalizedName:
    def test_mbc_from_bulletin_header(self):
        with patch(
            "app.modules.admin_import.infrastructure.repository.get_supabase_admin_client"
        ) as mock_client:
            mock_client.return_value.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
                data=[MBC_COMPANY, {"id": "co-2", "company_name": "Comitech", "siret": "x"}]
            )
            found = find_company_by_normalized_name("MONT BLANC COMPOSITE")
            assert found is not None
            assert found["id"] == "co-mbc"


class TestResolveCompanyFromPayslip:
    def test_name_fallback_when_siret_missing_in_db(self):
        with patch(
            "app.modules.admin_import.infrastructure.repository.find_company_by_siret",
            return_value=None,
        ), patch(
            "app.modules.admin_import.infrastructure.repository.find_company_by_normalized_name",
            return_value=MBC_COMPANY,
        ):
            company, warnings = resolve_company_from_payslip(
                "75116833700028",
                "MONT BLANC COMPOSITE",
            )
            assert company is not None
            assert company["id"] == "co-mbc"
            assert any("identifiée par nom" in w for w in warnings)
            assert not any("introuvable" in w for w in warnings)

    def test_unknown_company_still_errors(self):
        with patch(
            "app.modules.admin_import.infrastructure.repository.find_company_by_siret",
            return_value=None,
        ), patch(
            "app.modules.admin_import.infrastructure.repository.find_company_by_normalized_name",
            return_value=None,
        ):
            company, warnings = resolve_company_from_payslip(
                "75116833700028",
                "SOCIETE INCONNUE",
            )
            assert company is None
            assert any("introuvable" in w for w in warnings)
