"""
Tests unitaires du calcul de préavis (domain/notice_period.py).
"""

from datetime import date

import pytest

from app.modules.employee_exits.domain.notice_period import (
    compute_notice_period,
    compute_seniority_months,
    resolve_employee_category,
)


pytestmark = pytest.mark.unit


class TestResolveEmployeeCategory:
    def test_cadre(self):
        assert resolve_employee_category("Cadre") == ("cadre", True)

    def test_non_cadre(self):
        assert resolve_employee_category("Non-Cadre") == ("non_cadre", True)

    def test_empty_defaults_non_cadre(self):
        category, explicit = resolve_employee_category(None)
        assert category == "non_cadre"
        assert explicit is False


class TestComputeSeniorityMonths:
    def test_one_year(self):
        assert compute_seniority_months(date(2024, 1, 1), date(2025, 1, 1)) == 12


class TestComputeNoticePeriod:
    def test_no_collective_agreement_uses_legal_non_cadre(self):
        result = compute_notice_period(
            exit_type="demission",
            hire_date=date(2022, 1, 1),
            reference_date=date(2025, 6, 1),
            statut="Employé",
            collective_agreement_name=None,
            collective_agreement_idcc=None,
        )
        assert result.days == 60
        assert result.source == "legal"
        assert any("Aucune convention collective" in w for w in result.warnings)

    def test_cadre_two_years_legal(self):
        result = compute_notice_period(
            exit_type="demission",
            hire_date=date(2022, 1, 1),
            reference_date=date(2025, 6, 1),
            statut="Cadre",
        )
        assert result.days == 90
        assert result.employee_category == "cadre"

    def test_convention_overrides_legal(self):
        rules = {
            "preavis": {
                "demission": {
                    "non_cadre": [
                        {"anciennete_mois_min": 24, "jours": 75},
                    ]
                }
            }
        }
        result = compute_notice_period(
            exit_type="demission",
            hire_date=date(2022, 1, 1),
            reference_date=date(2025, 6, 1),
            statut="Employé",
            collective_agreement_name="Syntec",
            collective_agreement_idcc="1486",
            cc_rules=rules,
        )
        assert result.days == 75
        assert result.source == "convention"

    def test_convention_without_preavis_rules_falls_back_legal(self):
        result = compute_notice_period(
            exit_type="demission",
            hire_date=date(2022, 1, 1),
            reference_date=date(2025, 6, 1),
            statut="Employé",
            collective_agreement_name="Syntec",
            collective_agreement_idcc="1486",
            cc_rules={"prime_anciennete": {}},
        )
        assert result.days == 60
        assert result.source == "legal"
        assert any("Aucune règle de préavis extraite" in w for w in result.warnings)

    def test_rupture_conventionnelle_not_applicable(self):
        result = compute_notice_period(
            exit_type="rupture_conventionnelle",
            hire_date=date(2022, 1, 1),
            reference_date=date(2025, 6, 1),
            statut="Employé",
        )
        assert result.days == 0
        assert result.source == "not_applicable"
        assert result.applicable is False

    def test_gross_misconduct_zero(self):
        result = compute_notice_period(
            exit_type="licenciement",
            hire_date=date(2022, 1, 1),
            reference_date=date(2025, 6, 1),
            statut="Employé",
            is_gross_misconduct=True,
        )
        assert result.days == 0
        assert result.source == "not_applicable"

    def test_missing_hire_date_warns(self):
        result = compute_notice_period(
            exit_type="demission",
            hire_date=None,
            reference_date=date(2025, 6, 1),
            statut="Employé",
        )
        assert any("Date d'embauche" in w for w in result.warnings)

    def test_seniority_under_six_months(self):
        result = compute_notice_period(
            exit_type="demission",
            hire_date=date(2025, 4, 1),
            reference_date=date(2025, 6, 1),
            statut="Employé",
        )
        assert result.days == 0
        assert result.source == "legal"
