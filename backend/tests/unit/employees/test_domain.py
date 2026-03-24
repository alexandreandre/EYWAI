"""
Tests unitaires du domaine employees : règles métier et constantes.

Sans DB, sans HTTP. Couvre rules.py (build_employee_folder_name,
default_company_data_fallback, constantes). Les entités et value_objects
sont des placeholders vides dans ce module.
"""
import pytest

from app.modules.employees.domain.rules import (
    DEFAULT_EMPLOYMENT_STATUS,
    DEFAULT_RESIDENCE_PERMIT_SUBJECT,
    build_employee_folder_name,
    default_company_data_fallback,
)


pytestmark = pytest.mark.unit


class TestDomainConstants:
    """Constantes par défaut du domaine employees."""

    def test_default_employment_status_is_actif(self):
        assert DEFAULT_EMPLOYMENT_STATUS == "actif"

    def test_default_residence_permit_subject_is_false(self):
        assert DEFAULT_RESIDENCE_PERMIT_SUBJECT is False


class TestBuildEmployeeFolderName:
    """Règle build_employee_folder_name : nom de dossier employé."""

    def test_returns_last_upper_and_first_capitalized_joined_by_underscore(self):
        result = build_employee_folder_name("DUPONT", "Jean")
        assert result == "DUPONT_Jean"

    def test_handles_accents_already_normalized(self):
        result = build_employee_folder_name("MARTIN", "François")
        assert result == "MARTIN_François"

    def test_handles_single_char_names(self):
        result = build_employee_folder_name("A", "B")
        assert result == "A_B"

    def test_handles_long_names(self):
        result = build_employee_folder_name("DUPONT-MARTIN", "Jean-Pierre")
        assert result == "DUPONT-MARTIN_Jean-Pierre"


class TestDefaultCompanyDataFallback:
    """Règle default_company_data_fallback : données entreprise par défaut."""

    def test_returns_dict_with_expected_keys(self):
        data = default_company_data_fallback()
        assert "company_name" in data
        assert "siret" in data
        assert "email" in data

    def test_company_name_is_maji(self):
        data = default_company_data_fallback()
        assert data["company_name"] == "MAJI"

    def test_siret_is_na(self):
        data = default_company_data_fallback()
        assert data["siret"] == "N/A"

    def test_email_is_contact_maji(self):
        data = default_company_data_fallback()
        assert data["email"] == "contact@maji.com"

    def test_returns_new_dict_each_call(self):
        a = default_company_data_fallback()
        b = default_company_data_fallback()
        assert a is not b
        assert a == b
