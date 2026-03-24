"""
Tests unitaires du domaine payslips : entités, value objects, enums et règles métier.

Sans DB, sans HTTP. Couvre toutes les entités, value objects et règles du domain/.
"""
import pytest

from app.modules.payslips.domain.entities import Payslip
from app.modules.payslips.domain.value_objects import PayslipPeriod
from app.modules.payslips.domain.enums import PayslipGenerationMode
from app.modules.payslips.domain.rules import (
    is_forfait_jour,
    can_view_payslip,
    can_edit_or_restore_payslip,
)


# --- Entité Payslip ---


class TestPayslipEntity:
    """Tests de l'entité Payslip."""

    def test_from_row_builds_entity_with_required_fields(self):
        """from_row construit une entité à partir d'une ligne BDD complète."""
        row = {
            "id": "ps-1",
            "employee_id": "emp-1",
            "company_id": "co-1",
            "month": 3,
            "year": 2024,
            "payslip_data": {"net_a_payer": 2500.0},
        }
        payslip = Payslip.from_row(row)
        assert payslip.id == "ps-1"
        assert payslip.employee_id == "emp-1"
        assert payslip.company_id == "co-1"
        assert payslip.month == 3
        assert payslip.year == 2024
        assert payslip.payslip_data == {"net_a_payer": 2500.0}

    def test_from_row_uses_empty_dict_when_payslip_data_missing(self):
        """from_row utilise {} si payslip_data absent."""
        row = {
            "id": "ps-2",
            "employee_id": "emp-2",
            "company_id": "co-2",
            "month": 1,
            "year": 2025,
        }
        payslip = Payslip.from_row(row)
        assert payslip.payslip_data == {}

    def test_from_row_uses_empty_dict_when_payslip_data_none(self):
        """from_row utilise {} si payslip_data est None."""
        row = {
            "id": "ps-3",
            "employee_id": "emp-3",
            "company_id": "co-3",
            "month": 6,
            "year": 2024,
            "payslip_data": None,
        }
        payslip = Payslip.from_row(row)
        assert payslip.payslip_data == {}


# --- Value object PayslipPeriod ---


class TestPayslipPeriod:
    """Tests du value object PayslipPeriod."""

    def test_period_stores_year_and_month(self):
        """PayslipPeriod conserve year et month."""
        period = PayslipPeriod(year=2024, month=12)
        assert period.year == 2024
        assert period.month == 12

    def test_period_is_frozen(self):
        """PayslipPeriod est immutable (frozen)."""
        from dataclasses import FrozenInstanceError
        period = PayslipPeriod(year=2024, month=1)
        with pytest.raises(FrozenInstanceError):
            period.year = 2025  # type: ignore


# --- Enum PayslipGenerationMode ---


class TestPayslipGenerationMode:
    """Tests de l'enum PayslipGenerationMode."""

    def test_heures_value(self):
        """HEURES a la valeur attendue."""
        assert PayslipGenerationMode.HEURES == "heures"
        assert PayslipGenerationMode.HEURES.value == "heures"

    def test_forfait_jour_value(self):
        """FORFAIT_JOUR a la valeur attendue."""
        assert PayslipGenerationMode.FORFAIT_JOUR == "forfait_jour"
        assert PayslipGenerationMode.FORFAIT_JOUR.value == "forfait_jour"


# --- Règle is_forfait_jour ---


class TestIsForfaitJour:
    """Tests de la règle is_forfait_jour."""

    def test_returns_true_when_statut_contains_forfait_jour(self):
        """Retourne True si le statut contient 'forfait jour' (insensible à la casse)."""
        assert is_forfait_jour("Cadre forfait jour") is True
        assert is_forfait_jour("FORFAIT JOUR") is True
        assert is_forfait_jour("Forfait Jour") is True

    def test_returns_false_when_statut_does_not_contain_forfait_jour(self):
        """Retourne False si le statut ne contient pas 'forfait jour'."""
        assert is_forfait_jour("Cadre au forfait heures") is False
        assert is_forfait_jour("Employé") is False
        assert is_forfait_jour("") is False

    def test_returns_false_when_statut_is_none(self):
        """Retourne False si statut est None."""
        assert is_forfait_jour(None) is False


# --- Règle can_view_payslip ---


class TestCanViewPayslip:
    """Tests de la règle can_view_payslip."""

    def test_employee_can_view_own_payslip(self):
        """L'employé peut consulter son propre bulletin (employee_id == user_id)."""
        payslip = {"employee_id": "user-1", "company_id": "co-1"}
        assert can_view_payslip(
            payslip,
            user_id="user-1",
            is_super_admin=False,
            has_rh_access_in_company=lambda c: False,
            active_company_id="co-2",
        ) is True

    def test_super_admin_can_view_any_payslip(self):
        """Un super admin peut consulter n'importe quel bulletin."""
        payslip = {"employee_id": "emp-1", "company_id": "co-1"}
        assert can_view_payslip(
            payslip,
            user_id="other-user",
            is_super_admin=True,
            has_rh_access_in_company=lambda c: False,
            active_company_id=None,
        ) is True

    def test_rh_with_access_and_matching_company_can_view(self):
        """Un RH avec accès à l'entreprise du bulletin et entreprise active identique peut consulter."""
        payslip = {"employee_id": "emp-1", "company_id": "co-1"}
        assert can_view_payslip(
            payslip,
            user_id="rh-user",
            is_super_admin=False,
            has_rh_access_in_company=lambda c: c == "co-1",
            active_company_id="co-1",
        ) is True

    def test_rh_with_access_but_different_active_company_cannot_view(self):
        """Un RH avec accès à co-1 mais entreprise active co-2 ne peut pas consulter un bulletin co-1."""
        payslip = {"employee_id": "emp-1", "company_id": "co-1"}
        assert can_view_payslip(
            payslip,
            user_id="rh-user",
            is_super_admin=False,
            has_rh_access_in_company=lambda c: c == "co-1",
            active_company_id="co-2",
        ) is False

    def test_no_rh_access_returns_false(self):
        """Sans accès RH sur l'entreprise du bulletin, retourne False."""
        payslip = {"employee_id": "emp-1", "company_id": "co-1"}
        assert can_view_payslip(
            payslip,
            user_id="other-user",
            is_super_admin=False,
            has_rh_access_in_company=lambda c: False,
            active_company_id="co-1",
        ) is False

    def test_no_company_id_returns_false_for_non_owner(self):
        """Si le bulletin n'a pas de company_id et l'utilisateur n'est pas l'employé, retourne False."""
        payslip = {"employee_id": "emp-1", "company_id": None}
        assert can_view_payslip(
            payslip,
            user_id="other-user",
            is_super_admin=False,
            has_rh_access_in_company=lambda c: True,
            active_company_id="co-1",
        ) is False

    def test_active_company_none_rh_with_access_can_view(self):
        """Si active_company_id est None mais has_rh_access sur company_id, la règle accepte (pas de filtre actif)."""
        payslip = {"employee_id": "emp-1", "company_id": "co-1"}
        assert can_view_payslip(
            payslip,
            user_id="rh-user",
            is_super_admin=False,
            has_rh_access_in_company=lambda c: c == "co-1",
            active_company_id=None,
        ) is True


# --- Règle can_edit_or_restore_payslip ---


class TestCanEditOrRestorePayslip:
    """Tests de la règle can_edit_or_restore_payslip."""

    def test_super_admin_can_edit_any(self):
        """Un super admin peut éditer/restaurer n'importe quel bulletin."""
        payslip = {"employee_id": "emp-1", "company_id": "co-1"}
        assert can_edit_or_restore_payslip(
            payslip,
            is_super_admin=True,
            has_rh_access_in_company=lambda c: False,
            active_company_id=None,
        ) is True

    def test_rh_with_access_and_matching_company_can_edit(self):
        """Un RH avec accès et entreprise active identique peut éditer."""
        payslip = {"employee_id": "emp-1", "company_id": "co-1"}
        assert can_edit_or_restore_payslip(
            payslip,
            is_super_admin=False,
            has_rh_access_in_company=lambda c: c == "co-1",
            active_company_id="co-1",
        ) is True

    def test_rh_with_access_but_different_active_company_cannot_edit(self):
        """Un RH avec accès à co-1 mais entreprise active co-2 ne peut pas éditer un bulletin co-1."""
        payslip = {"employee_id": "emp-1", "company_id": "co-1"}
        assert can_edit_or_restore_payslip(
            payslip,
            is_super_admin=False,
            has_rh_access_in_company=lambda c: c == "co-1",
            active_company_id="co-2",
        ) is False

    def test_no_company_id_returns_false(self):
        """Si le bulletin n'a pas de company_id, retourne False (sauf super admin)."""
        payslip = {"employee_id": "emp-1", "company_id": None}
        assert can_edit_or_restore_payslip(
            payslip,
            is_super_admin=False,
            has_rh_access_in_company=lambda c: True,
            active_company_id="co-1",
        ) is False

    def test_no_rh_access_returns_false(self):
        """Sans accès RH sur l'entreprise, retourne False."""
        payslip = {"employee_id": "emp-1", "company_id": "co-1"}
        assert can_edit_or_restore_payslip(
            payslip,
            is_super_admin=False,
            has_rh_access_in_company=lambda c: False,
            active_company_id="co-1",
        ) is False
