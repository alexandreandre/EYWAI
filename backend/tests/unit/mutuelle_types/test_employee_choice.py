"""Tests règles choix mutuelle salarié."""

from app.modules.mutuelle_types.domain.employee_choice import (
    is_mutuelle_eligible_for_employee,
    resolve_organisme_label,
)


class TestMutuelleEligibility:
    def test_cadre_formula_for_cadre_employee(self):
        assert is_mutuelle_eligible_for_employee(
            {"is_active": True, "statut_categoriel": "cadre"},
            "Cadre au forfait jour",
        )

    def test_cadre_formula_rejected_for_non_cadre(self):
        assert not is_mutuelle_eligible_for_employee(
            {"is_active": True, "statut_categoriel": "cadre"},
            "Non-Cadre",
        )

    def test_inactive_formula_rejected(self):
        assert not is_mutuelle_eligible_for_employee(
            {"is_active": False, "statut_categoriel": "tous"},
            "Cadre",
        )


class TestOrganismeLabel:
    def test_formula_label_priority(self):
        assert resolve_organisme_label({"organisme_label": "APICIL"}, "Generali") == "APICIL"

    def test_company_fallback(self):
        assert resolve_organisme_label({}, "APICIL") == "APICIL"
