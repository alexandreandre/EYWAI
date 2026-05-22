"""Tests unitaires domain/overview et query get_company_overview."""

from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import pytest

from app.modules.companies.application import queries
from app.modules.companies.application.dto import CompanyOverviewDto
from app.modules.companies.domain.overview import (
    compute_alerts,
    compute_demographics,
    compute_movements,
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
                },
            ):
                result = queries.get_company_overview("c1", MagicMock())
        assert isinstance(result, CompanyOverviewDto)
        assert result.demographics["total_headcount"] == 1
