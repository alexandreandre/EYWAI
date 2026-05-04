"""
Repository dashboard : implémentation de IDashboardDataReader.

Délègue aux fonctions de infrastructure.queries (Supabase).
"""

from __future__ import annotations

from datetime import date

from app.modules.dashboard.domain.interfaces import IDashboardDataReader
from app.modules.dashboard.infrastructure import queries


class DashboardRepository:
    """Lit les données brutes nécessaires à l'agrégation dashboard."""

    def get_employees_for_dashboard(self, company_id: str) -> list:
        return queries.fetch_employees_for_dashboard(company_id)

    def get_absence_requests_validated_today(self, company_id: str) -> list:
        today_iso = date.today().isoformat()
        return queries.fetch_absences_validated_today(company_id, today_iso)

    def get_absence_requests_for_absenteeism(self, company_id: str) -> list:
        return queries.fetch_absence_requests_for_absenteeism(company_id)

    def get_payslips_by_company(self, company_id: str) -> list:
        return queries.fetch_payslips_by_company(company_id)

    def get_pending_expense_reports_count(self, company_id: str) -> int:
        return queries.get_pending_expense_reports_count(company_id)

    def get_pending_absence_requests_count(self, company_id: str) -> int:
        return queries.get_pending_absence_requests_count(company_id)

    def get_employees_for_residence_permit_stats(self, company_id: str) -> list:
        return queries.fetch_employees_for_residence_permit_stats(company_id)

    def count_employees_missing_iban(self, company_id: str) -> int:
        return queries.count_employees_missing_iban(company_id)

    def count_monthly_inputs_for_company(self, company_id: str, year: int, month: int) -> int:
        return queries.count_monthly_inputs_for_company(company_id, year, month)

    def salary_advances_summary_for_company(
        self, company_id: str, ref_year: int, ref_month: int
    ) -> tuple[int, float, int, float]:
        return queries.salary_advances_summary_for_company(company_id, ref_year, ref_month)


def get_dashboard_repository() -> IDashboardDataReader:
    """Retourne une implémentation de IDashboardDataReader."""
    return DashboardRepository()
