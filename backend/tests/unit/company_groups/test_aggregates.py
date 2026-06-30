"""Tests unitaires agrégation stats groupe."""

from app.modules.company_groups.application.aggregates import (
    aggregate_consolidated_dashboards,
    resolve_comparison_period,
)


def _monthly(company_id: str, gross: float, employees: int) -> dict:
    return {
        "metadata": {"reference_year": 2024, "reference_month": 1, "company_count": 1},
        "totals": {},
        "by_company": [
            {
                "company_id": company_id,
                "company_name": "Co",
                "total_employee_count": employees,
                "employee_count": employees - 1,
                "active_employee_count": employees - 2,
                "rh_count": 1,
                "payslip_count": 1,
                "gross_salary": gross,
                "net_salary": gross * 0.75,
                "employer_charges": gross * 0.4,
            }
        ],
    }


class TestAggregateConsolidatedDashboards:
    def test_sums_payroll_and_averages_headcount(self):
        m1 = _monthly("c1", 1000, 10)
        m2 = _monthly("c1", 2000, 20)
        result = aggregate_consolidated_dashboards(
            [m1, m2],
            start_year=2024,
            start_month=1,
            end_year=2024,
            end_month=2,
        )
        assert len(result["by_company"]) == 1
        row = result["by_company"][0]
        assert row["gross_salary"] == 3000
        assert row["total_employee_count"] == 15  # moyenne 10 et 20
        assert row["active_employee_count"] == 13
        assert result["totals"]["total_active_employees_excluding_rh"] == 13

    def test_empty_returns_empty_structure(self):
        result = aggregate_consolidated_dashboards(
            [],
            start_year=2024,
            start_month=1,
            end_year=2024,
            end_month=2,
        )
        assert result["by_company"] == []


class TestResolveComparisonPeriod:
    def test_previous_month_single(self):
        bounds = resolve_comparison_period("previous_month", year=2024, month=6)
        assert bounds == (2024, 5, 2024, 5)

    def test_previous_year_range(self):
        bounds = resolve_comparison_period(
            "previous_year",
            start_year=2024,
            start_month=1,
            end_year=2024,
            end_month=12,
        )
        assert bounds == (2023, 1, 2023, 12)
