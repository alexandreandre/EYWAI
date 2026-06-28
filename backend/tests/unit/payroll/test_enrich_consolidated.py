"""Tests enrichissement DSN vue consolidée groupe."""

from unittest.mock import MagicMock, patch

from app.modules.payroll.application.payroll_kpi_queries import (
    ConsolidatedPayrollContext,
    enrich_consolidated_with_dsn,
)
from app.modules.payroll.domain.payroll_kpi_resolver import (
    DsnPeriodTotals,
    PayrollPeriodSnapshot,
    PayslipPeriodTotals,
)


def _snapshot(
    *,
    source: str = "dsn",
    gross: float = 5000.0,
    net: float = 3800.0,
    employer_charges: float = 2100.0,
) -> PayrollPeriodSnapshot:
    return PayrollPeriodSnapshot(
        period="2024-06",
        source=source,  # type: ignore[arg-type]
        source_label="DSN",
        gross=gross,
        net=net,
        employer_cost=gross + employer_charges,
        employee_charges=500.0,
        employer_charges=employer_charges,
    )


class TestEnrichConsolidatedWithDsn:
    def test_fills_dsn_amounts_and_charges(self):
        payload = {
            "metadata": {"reference_year": 2024, "reference_month": 6},
            "totals": {},
            "by_company": [
                {
                    "company_id": "c1",
                    "company_name": "Co",
                    "gross_salary": 0,
                    "net_salary": 0,
                    "employer_charges": 0,
                }
            ],
        }
        ctx = ConsolidatedPayrollContext(
            modes={"c1": "transition"},
            payslips_by_company={"c1": []},
            dsn_by_company_period={"c1": {"2024-06": DsnPeriodTotals(gross=5000, net_imposable=3800, employer_charges=2100)}},
        )

        result = enrich_consolidated_with_dsn(payload, ["c1"], "2024-06", ctx=ctx)

        row = result["by_company"][0]
        assert row["gross_salary"] == 5000.0
        assert row["net_salary"] == 3800.0
        assert row["employer_charges"] == 2100.0
        assert row["payroll_source"] == "dsn"
        assert result["totals"]["total_gross_salary"] == 5000.0
        assert result["totals"]["total_employer_charges"] == 2100.0

    def test_keeps_payslip_row_and_backfills_charges(self):
        payload = {
            "metadata": {},
            "totals": {},
            "by_company": [
                {
                    "company_id": "c1",
                    "gross_salary": 4000,
                    "net_salary": 3000,
                    "employer_charges": 0,
                }
            ],
        }
        ctx = MagicMock()
        ctx.resolve_snapshot.return_value = _snapshot(
            source="payslip", gross=4000, net=3000, employer_charges=1800
        )

        result = enrich_consolidated_with_dsn(payload, ["c1"], "2024-06", ctx=ctx)

        row = result["by_company"][0]
        assert row["payroll_source"] == "payslip"
        assert row["employer_charges"] == 1800.0
        assert result["totals"]["total_employer_charges"] == 1800.0


class TestEnrichPayrollEvolutionWithDsn:
    def test_fills_zero_gross_points_from_dsn(self):
        from app.modules.payroll.application.payroll_kpi_queries import (
            enrich_payroll_evolution_with_dsn,
        )

        points = [
            {
                "company_id": "c1",
                "company_name": "Co",
                "year": 2024,
                "month": 6,
                "total_gross": 0,
                "total_net": 0,
                "total_employer_charges": 0,
                "employee_count": 0,
            }
        ]
        ctx = ConsolidatedPayrollContext(
            modes={"c1": "transition"},
            payslips_by_company={"c1": []},
            dsn_by_company_period={
                "c1": {
                    "2024-06": DsnPeriodTotals(
                        gross=5000,
                        net_imposable=3800,
                        employer_charges=2100,
                        employee_count=12,
                    )
                }
            },
        )

        result = enrich_payroll_evolution_with_dsn(points, ["c1"], ctx=ctx)

        assert result[0]["total_gross"] == 5000.0
        assert result[0]["total_net"] == 3800.0
        assert result[0]["total_employer_charges"] == 2100.0
        assert result[0]["employee_count"] == 12


class TestFetchConsolidatedMultiMonthDsn:
    MODULE = "app.modules.company_groups.application.queries"

    def test_enriches_each_month_before_aggregation(self):
        from app.modules.company_groups.application import queries

        mock_repo = MagicMock()
        mock_repo.get_companies_for_group_stats.return_value = [{"id": "c1"}]
        user = MagicMock()
        user.is_platform_admin = True

        month_a = {
            "metadata": {"reference_year": 2024, "reference_month": 1},
            "totals": {},
            "by_company": [{"company_id": "c1", "gross_salary": 0, "employer_charges": 0}],
        }
        month_b = {
            "metadata": {"reference_year": 2024, "reference_month": 2},
            "totals": {},
            "by_company": [{"company_id": "c1", "gross_salary": 0, "employer_charges": 0}],
        }

        def _enrich(payload, _ids, period, *, ctx=None):
            gross = 1000.0 if period.endswith("-01") else 2000.0
            charges = 400.0 if period.endswith("-01") else 800.0
            row = payload["by_company"][0]
            row["gross_salary"] = gross
            row["employer_charges"] = charges
            payload["totals"]["total_gross_salary"] = gross
            payload["totals"]["total_employer_charges"] = charges
            return payload

        with (
            patch(f"{self.MODULE}.company_group_repository", mock_repo),
            patch(f"{self.MODULE}.get_company_ids_for_group", return_value=["c1"]),
            patch(
                f"{self.MODULE}.call_get_group_consolidated_dashboard",
                side_effect=[month_a, month_b],
            ),
            patch(
                "app.modules.payroll.application.payroll_kpi_queries.ConsolidatedPayrollContext.build",
                return_value=MagicMock(),
            ),
            patch(
                "app.modules.payroll.application.payroll_kpi_queries.enrich_consolidated_with_dsn",
                side_effect=_enrich,
            ) as enrich_mock,
        ):
            result = queries.get_group_consolidated_stats(
                "g1",
                user,
                start_year=2024,
                start_month=1,
                end_year=2024,
                end_month=2,
            )

        assert enrich_mock.call_count == 2
        assert result["by_company"][0]["gross_salary"] == 3000
        assert result["by_company"][0]["employer_charges"] == 1200
