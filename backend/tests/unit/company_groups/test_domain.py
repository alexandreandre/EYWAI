"""
Tests unitaires du domaine company_groups : entités, value objects, règles pures.

Sans DB, sans HTTP. Couvre CompanyGroup, CompanyInGroupRef et les règles
(validate_group_name, validate_siren, validate_group_create_data, validate_metric_for_comparison).
"""

from datetime import datetime

import pytest

from app.modules.company_groups.domain.entities import CompanyGroup, CompanyInGroupRef
from app.modules.company_groups.domain.rules import (
    SIREN_PATTERN,
    validate_group_create_data,
    validate_group_name,
    validate_metric_for_comparison,
    validate_siren,
)


# --- Entité CompanyGroup ---


class TestCompanyGroupEntity:
    """Entité CompanyGroup : agrégat groupe d'entreprises."""

    def test_company_group_creation_minimal(self):
        """Création avec id et group_name obligatoires."""
        g = CompanyGroup(id="g1", group_name="Groupe Test")
        assert g.id == "g1"
        assert g.group_name == "Groupe Test"
        assert g.is_active is True
        assert g.created_at is None
        assert g.updated_at is None
        assert g.siren is None
        assert g.description is None
        assert g.logo_url is None
        assert g.logo_scale == 1.0
        assert g.settings is None

    def test_company_group_creation_full(self):
        """Création avec tous les champs."""
        now = datetime.now()
        g = CompanyGroup(
            id="g2",
            group_name="Holding XYZ",
            is_active=False,
            created_at=now,
            updated_at=now,
            siren="123456789",
            description="Description du groupe",
            logo_url="https://example.com/logo.png",
            logo_scale=0.8,
            settings={"key": "value"},
        )
        assert g.siren == "123456789"
        assert g.description == "Description du groupe"
        assert g.logo_url == "https://example.com/logo.png"
        assert g.logo_scale == 0.8
        assert g.settings == {"key": "value"}
        assert g.is_active is False
        assert g.created_at == now
        assert g.updated_at == now

    def test_company_group_equality_by_identity(self):
        """Deux CompanyGroup avec le même id ont la même identité (agrégat)."""
        g1 = CompanyGroup(id="same", group_name="A")
        g2 = CompanyGroup(id="same", group_name="B")
        assert g1.id == g2.id


# --- Entité CompanyInGroupRef ---


class TestCompanyInGroupRefEntity:
    """Référence à une entreprise dans un groupe."""

    def test_company_in_group_ref_minimal(self):
        """Création avec id et company_name."""
        ref = CompanyInGroupRef(id="c1", company_name="Société A")
        assert ref.id == "c1"
        assert ref.company_name == "Société A"
        assert ref.siret is None
        assert ref.is_active is True

    def test_company_in_group_ref_full(self):
        """Création avec siret et is_active."""
        ref = CompanyInGroupRef(
            id="c2",
            company_name="Société B",
            siret="12345678901234",
            is_active=False,
        )
        assert ref.siret == "12345678901234"
        assert ref.is_active is False


# --- Règles : validate_group_name ---


class TestValidateGroupName:
    """validate_group_name : nom non vide après strip."""

    def test_none_returns_false(self):
        assert validate_group_name(None) is False

    def test_empty_string_returns_false(self):
        assert validate_group_name("") is False

    def test_whitespace_only_returns_false(self):
        assert validate_group_name("   ") is False
        assert validate_group_name("\t\n") is False

    def test_non_empty_returns_true(self):
        assert validate_group_name("Mon Groupe") is True
        assert validate_group_name("  Mon Groupe  ") is True

    def test_strip_applied(self):
        """La validation utilise strip : espaces seuls = invalide."""
        assert validate_group_name(" x ") is True


# --- Règles : validate_siren ---


class TestValidateSiren:
    """validate_siren : 9 chiffres si renseigné, optionnel."""

    def test_none_returns_true(self):
        """SIREN optionnel : None accepté."""
        assert validate_siren(None) is True

    def test_empty_or_whitespace_returns_true(self):
        assert validate_siren("") is True
        assert validate_siren("   ") is True

    def test_nine_digits_returns_true(self):
        assert validate_siren("123456789") is True
        assert validate_siren("  123456789  ") is True

    def test_wrong_length_returns_false(self):
        assert validate_siren("12345678") is False
        assert validate_siren("1234567890") is False

    def test_non_digits_returns_false(self):
        assert validate_siren("12345678X") is False
        assert validate_siren("12345-789") is False
        assert validate_siren("abcdefghi") is False


# --- Règles : validate_group_create_data ---


class TestValidateGroupCreateData:
    """validate_group_create_data : lève ValueError si invalide."""

    def test_valid_data_passes(self):
        """group_name non vide, siren optionnel valide ou absent."""
        validate_group_create_data({"group_name": "Groupe OK"})
        validate_group_create_data({"group_name": "Groupe", "siren": "123456789"})

    def test_missing_group_name_raises(self):
        with pytest.raises(ValueError, match="group_name est requis"):
            validate_group_create_data({})

    def test_empty_group_name_raises(self):
        with pytest.raises(ValueError, match="group_name est requis"):
            validate_group_create_data({"group_name": ""})
        with pytest.raises(ValueError, match="group_name est requis"):
            validate_group_create_data({"group_name": "   "})

    def test_invalid_siren_raises(self):
        with pytest.raises(
            ValueError, match="siren doit contenir exactement 9 chiffres"
        ):
            validate_group_create_data({"group_name": "Groupe", "siren": "12345"})


# --- Règles : validate_metric_for_comparison ---


class TestValidateMetricForComparison:
    """validate_metric_for_comparison : employees, payroll, absences."""

    def test_employees_valid(self):
        assert validate_metric_for_comparison("employees") is True

    def test_payroll_valid(self):
        assert validate_metric_for_comparison("payroll") is True

    def test_absences_valid(self):
        assert validate_metric_for_comparison("absences") is True

    def test_unknown_metric_invalid(self):
        assert validate_metric_for_comparison("revenue") is False
        assert validate_metric_for_comparison("") is False
        assert validate_metric_for_comparison("EMPLOYEES") is False


# --- SIREN_PATTERN (règle utilisée en interne) ---


class TestSirenPattern:
    """Pattern regex SIREN 9 chiffres."""

    def test_matches_nine_digits(self):
        assert SIREN_PATTERN.match("123456789") is not None

    def test_no_match_eight_digits(self):
        assert SIREN_PATTERN.match("12345678") is None

    def test_no_match_letters(self):
        assert SIREN_PATTERN.match("12345678X") is None
