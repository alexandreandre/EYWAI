"""Tests unitaires domain/overview et query get_company_overview."""

from datetime import date, timedelta
from unittest.mock import MagicMock, patch


from app.modules.companies.application import queries
from app.modules.companies.application.dto import CompanyOverviewDto
from app.modules.companies.domain.overview import (
    compute_alerts,
    compute_compliance_flags,
    compute_demographics,
    compute_movements,
    has_company_cc_assigned,
    is_jei_company_configured,
)


MODULE = "app.modules.companies.application.queries"


class TestComputeDemographics:
    def test_headcount_and_cadre_percent(self):
        employees = [
            {
                "id": "1",
                "statut": "Cadre",
                "hire_date": (date.today() - timedelta(days=400)).isoformat(),
                "weekly_hours": 35,
                "employment_status": "actif",
            },
            {
                "id": "2",
                "statut": "Non-cadre",
                "hire_date": (date.today() - timedelta(days=800)).isoformat(),
                "weekly_hours": 17.5,
                "employment_status": "actif",
            },
        ]
        result = compute_demographics(employees)
        assert result["total_headcount"] == 2
        assert result["total_etp"] == 1.5
        assert result["cadre_percent"] == 50.0


class TestComputeMovements:
    def test_hires_and_turnover(self):
        today = date.today()
        employees = [
            {"id": "1", "hire_date": today.isoformat()},
            {"id": "2", "hire_date": (today - timedelta(days=400)).isoformat()},
        ]
        exits = [
            {"exit_date": (today - timedelta(days=10)).isoformat()},
        ]
        result = compute_movements(employees, exits)
        assert result["new_hires_30_days"] >= 1
        assert result["exits_30_days"] == 1


class TestComputeAlerts:
    def test_missing_at_mp_alert(self):
        company = {"company_name": "Test", "taux_at_mp": None, "taux_vm": 0.01}
        alerts = compute_alerts(company, [], set())
        codes = [a["code"] for a in alerts]
        assert "missing_at_mp" in codes

    def test_missing_company_cc_alert_only(self):
        company = {"company_name": "Test", "taux_at_mp": 0.01, "taux_vm": 0.01}
        employees = [
            {
                "id": "e1",
                "first_name": "Alice",
                "last_name": "Martin",
                "employment_status": "actif",
                "collective_agreement_id": None,
            }
        ]
        alerts = compute_alerts(company, employees, set(), set())
        codes = [a["code"] for a in alerts]
        assert "missing_company_collective_agreement" in codes
        assert "employees_without_collective_agreement" not in codes
        company_alert = next(
            a for a in alerts if a["code"] == "missing_company_collective_agreement"
        )
        assert company_alert["action"] == "company_payroll_cc"

    def test_employees_without_cc_when_company_has_cc(self):
        company = {"company_name": "Test", "taux_at_mp": 0.01, "taux_vm": 0.01}
        employees = [
            {
                "id": "e1",
                "first_name": "Alice",
                "last_name": "Martin",
                "employment_status": "actif",
                "collective_agreement_id": None,
            },
            {
                "id": "e2",
                "first_name": "Bob",
                "last_name": "Durand",
                "employment_status": "actif",
                "collective_agreement_id": "cc-1",
            },
            {
                "id": "e3",
                "first_name": "Claire",
                "last_name": "Petit",
                "employment_status": "en_sortie",
                "collective_agreement_id": None,
            },
        ]
        alerts = compute_alerts(company, employees, set(), {"cc-1"})
        codes = [a["code"] for a in alerts]
        assert "missing_company_collective_agreement" not in codes
        assert "employees_without_collective_agreement" in codes
        emp_alert = next(
            a for a in alerts if a["code"] == "employees_without_collective_agreement"
        )
        assert emp_alert["count"] == 1
        assert emp_alert["employee_ids"] == ["e1"]
        assert len(emp_alert["employees"]) == 1


class TestComputeComplianceFlags:
    def test_collective_agreement_from_assignments(self):
        flags = compute_compliance_flags({}, 5, {"cc-1"})
        assert flags["collective_agreement_configured"] is True

    def test_collective_agreement_missing_without_assignments(self):
        flags = compute_compliance_flags({"idcc": "1486"}, 5, set())
        assert flags["collective_agreement_configured"] is False

    def test_jei_configured_when_enabled_with_date(self):
        flags = compute_compliance_flags(
            {},
            5,
            set(),
            {"jei_enabled": True, "date_creation_etablissement": "2024-01-01"},
        )
        assert flags["jei_configured"] is True

    def test_jei_not_configured_when_enabled_without_date(self):
        flags = compute_compliance_flags(
            {},
            5,
            set(),
            {"jei_enabled": True, "date_creation_etablissement": None},
        )
        assert flags["jei_configured"] is False


class TestJeiAlerts:
    def test_jei_enabled_no_rd_employees_alert(self):
        company = {"taux_at_mp": 0.01, "taux_vm": 0.01}
        employees = [
            {
                "id": "e1",
                "employment_status": "actif",
                "specificites_paie": {},
            }
        ]
        jei = {"jei_enabled": True, "date_creation_etablissement": "2024-06-01"}
        alerts = compute_alerts(company, employees, set(), {"cc-1"}, jei)
        codes = [a["code"] for a in alerts]
        assert "jei_enabled_no_rd_employees" in codes

    def test_jei_rd_without_company_status_alert(self):
        company = {"taux_at_mp": 0.01, "taux_vm": 0.01}
        employees = [
            {
                "id": "e1",
                "first_name": "Bob",
                "last_name": "Durand",
                "employment_status": "actif",
                "specificites_paie": {"personnel_rd_eligible_jei": True},
            }
        ]
        alerts = compute_alerts(company, employees, set(), {"cc-1"}, None)
        codes = [a["code"] for a in alerts]
        assert "jei_rd_without_company_status" in codes


class TestIsJeiCompanyConfigured:
    def test_requires_enabled_and_date(self):
        assert is_jei_company_configured(None) is False
        assert is_jei_company_configured({"jei_enabled": True}) is False
        assert is_jei_company_configured(
            {"jei_enabled": True, "date_creation_etablissement": "2020-01-01"}
        ) is True


class TestHasCompanyCcAssigned:
    def test_empty(self):
        assert has_company_cc_assigned(set()) is False

    def test_with_ids(self):
        assert has_company_cc_assigned({"cc-1"}) is True


class TestGetCompanyOverview:
    def test_returns_dto(self):
        company = {"id": "c1", "company_name": "ACME", "taux_at_mp": 0.01}
        with patch(f"{MODULE}.company_repository") as mock_repo:
            mock_repo.get_by_id.return_value = company
            with patch(
                f"{MODULE}.fetch_overview_raw",
                return_value={
                    "employees": [
                        {
                            "id": "e1",
                            "hire_date": date.today().isoformat(),
                            "employment_status": "actif",
                            "weekly_hours": 35,
                        }
                    ],
                    "exits": [],
                    "absences": [],
                    "mutuelle_employee_ids": set(),
                    "company_cc_ids": set(),
                    "jei_settings": None,
                },
            ):
                result = queries.get_company_overview("c1", MagicMock())
        assert isinstance(result, CompanyOverviewDto)
        assert result.demographics["total_headcount"] == 1
