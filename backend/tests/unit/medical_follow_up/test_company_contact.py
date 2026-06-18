"""
Tests unitaires de company_contact (infrastructure medical_follow_up).
"""

from unittest.mock import MagicMock, patch

from app.modules.medical_follow_up.infrastructure.company_contact import (
    get_occupational_health_contact,
)


@patch("app.modules.medical_follow_up.infrastructure.company_contact.get_supabase")
class TestGetOccupationalHealthContact:
    def test_returns_none_when_company_missing(self, mock_get_supabase):
        mock_get_supabase.return_value.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
            data=None
        )
        assert get_occupational_health_contact("co-1") is None

    def test_returns_none_when_all_fields_empty(self, mock_get_supabase):
        mock_get_supabase.return_value.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
            data={
                "service_sante_travail_nom": "",
                "service_sante_travail_adresse_rue": None,
                "service_sante_travail_adresse_code_postal": None,
                "service_sante_travail_adresse_ville": None,
                "service_sante_travail_telephone": None,
                "service_sante_travail_email": None,
            }
        )
        assert get_occupational_health_contact("co-1") is None

    def test_returns_contact_when_fields_present(self, mock_get_supabase):
        mock_get_supabase.return_value.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
            data={
                "service_sante_travail_nom": " SPSTI Test ",
                "service_sante_travail_adresse_rue": "1 rue Santé",
                "service_sante_travail_adresse_code_postal": "44000",
                "service_sante_travail_adresse_ville": "Nantes",
                "service_sante_travail_telephone": "02 40 00 00 00",
                "service_sante_travail_email": "contact@spst.test",
            }
        )
        contact = get_occupational_health_contact("co-1")
        assert contact == {
            "nom": "SPSTI Test",
            "adresse_rue": "1 rue Santé",
            "adresse_code_postal": "44000",
            "adresse_ville": "Nantes",
            "telephone": "02 40 00 00 00",
            "email": "contact@spst.test",
        }
