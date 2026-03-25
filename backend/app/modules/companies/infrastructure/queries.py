"""
Requêtes métier complexes (lecture) companies.

Implémentation de ICompanyDetailsProvider (DB Supabase).
Pas de logique métier : uniquement accès données.
"""

from typing import Any, Dict, Optional

from app.core.database import supabase
from app.modules.companies.domain.interfaces import ICompanyDetailsProvider


class SupabaseCompanyDetailsProvider(ICompanyDetailsProvider):
    """
    Récupération company + employees + payslips et company_id depuis profil.
    Comportement identique aux appels du routeur legacy.
    """

    def get_company_with_employees_and_payslips(
        self, company_id: str
    ) -> Dict[str, Any]:
        company_res = (
            supabase.table("companies")
            .select("*")
            .eq("id", company_id)
            .single()
            .execute()
        )
        if not company_res.data:
            return {"company_data": None, "employees": [], "payslips": []}

        employees_res = (
            supabase.table("employees")
            .select("id, contract_type, hire_date, job_title")
            .eq("company_id", company_id)
            .execute()
        )
        payslips_res = (
            supabase.table("payslips")
            .select("month, year, payslip_data")
            .eq("company_id", company_id)
            .execute()
        )

        return {
            "company_data": company_res.data,
            "employees": employees_res.data or [],
            "payslips": payslips_res.data or [],
        }

    def get_company_id_from_profile(self, user_id: str) -> Optional[str]:
        r = (
            supabase.table("profiles")
            .select("company_id")
            .eq("id", str(user_id))
            .single()
            .execute()
        )
        if not r.data or not r.data.get("company_id"):
            return None
        return r.data["company_id"]


# Instance partagée
_company_details_provider = SupabaseCompanyDetailsProvider()


def fetch_company_with_employees_and_payslips(company_id: str) -> Dict[str, Any]:
    """Délègue à ICompanyDetailsProvider (compatibilité application)."""
    return _company_details_provider.get_company_with_employees_and_payslips(company_id)


def get_company_id_from_profile(user_id: str) -> Optional[str]:
    """Délègue à ICompanyDetailsProvider (compatibilité application)."""
    return _company_details_provider.get_company_id_from_profile(user_id)
