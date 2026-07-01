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
    DUREE_LEGALE_HEBDO,
    build_employee_folder_name,
    default_company_data_fallback,
    derive_collaborator_username,
    is_dsn_import_placeholder_email,
    is_import_style_username,
    is_temps_travail_incoherent,
    normalize_temps_travail_fields,
    resolve_unique_collaborator_username,
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

    def test_company_name_is_generic(self):
        data = default_company_data_fallback()
        assert data["company_name"] == "Entreprise"

    def test_siret_is_empty(self):
        data = default_company_data_fallback()
        assert data["siret"] == ""

    def test_email_is_empty(self):
        data = default_company_data_fallback()
        assert data["email"] == ""

    def test_returns_new_dict_each_call(self):
        a = default_company_data_fallback()
        b = default_company_data_fallback()
        assert a is not b
        assert a == b


class TestDeriveCollaboratorUsername:
    def test_uses_prenom_nom_even_when_email_differs(self):
        username = derive_collaborator_username(
            "Camille",
            "RecruteRH",
            email="camille.recruterh.714b28@eywai-demo.com",
        )
        assert username == "camille.recruterh"

    def test_falls_back_to_first_last_without_email(self):
        username = derive_collaborator_username("Jean", "Dupont")
        assert username == "jean.dupont"

    def test_keeps_existing_username_when_provided(self):
        username = derive_collaborator_username(
            "Jean",
            "Dupont",
            email="jean.dupont@example.com",
            existing="custom.user",
        )
        assert username == "custom.user"

    def test_replaces_import_style_existing_username(self):
        username = derive_collaborator_username(
            "Samir",
            "Boufrida",
            existing="import.samir.boufrida.353238",
        )
        assert username == "samir.boufrida"

    def test_normalizes_accents_and_hyphens(self):
        username = derive_collaborator_username("François", "Dupont-Martin")
        assert username == "francois.dupont_martin"


class TestResolveUniqueCollaboratorUsername:
    def test_returns_base_when_available(self):
        username = resolve_unique_collaborator_username(
            "jean.dupont",
            {"marie.martin"},
        )
        assert username == "jean.dupont"

    def test_appends_numeric_suffix_on_collision(self):
        username = resolve_unique_collaborator_username(
            "jean.dupont",
            {"jean.dupont", "marie.martin"},
        )
        assert username == "jean.dupont2"

    def test_increments_suffix_until_available(self):
        username = resolve_unique_collaborator_username(
            "jean.dupont",
            {"jean.dupont", "jean.dupont2", "jean.dupont3"},
        )
        assert username == "jean.dupont4"


class TestIsImportStyleUsername:
    def test_detects_import_prefix(self):
        assert is_import_style_username("import.samir.boufrida.353238")
        assert not is_import_style_username("samir.boufrida")


class TestIsDsnImportPlaceholderEmail:
    def test_detects_placeholder_suffix(self):
        assert is_dsn_import_placeholder_email(
            "import.samir.boufrida.353238@498610351.dsn-import.local"
        )
        assert not is_dsn_import_placeholder_email("samir.boufrida@cartol.fr")
        assert not is_dsn_import_placeholder_email(None)


class TestNormalizeTempsTravailFields:
    def test_duree_inferieure_35_force_temps_partiel(self):
        is_tp, duree = normalize_temps_travail_fields(False, 28.0)
        assert is_tp is True
        assert duree == 28.0

    def test_duree_35_sans_flag_temps_plein(self):
        is_tp, duree = normalize_temps_travail_fields(None, 35.0)
        assert is_tp is False
        assert duree == 35.0

    def test_flag_tp_conserve_avec_duree_35_pour_relecture(self):
        is_tp, duree = normalize_temps_travail_fields(True, 35.0)
        assert is_tp is True
        assert duree == 35.0

    def test_incoherence_detectee(self):
        assert is_temps_travail_incoherent(True, 35.0) is True
        assert is_temps_travail_incoherent(True, 14.0) is False
        assert is_temps_travail_incoherent(False, 35.0) is False

    def test_duree_legale_hebdo(self):
        assert DUREE_LEGALE_HEBDO == 35.0
