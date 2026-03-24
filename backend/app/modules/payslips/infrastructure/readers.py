"""
Readers infrastructure : implémentation des ports domain (IEmployeeStatutReader, IPayslipMetaReader, IDebugStorageInfoProvider).

Délèguent aux queries pour statut/meta ; pas de FastAPI.
"""
from __future__ import annotations

import requests
from typing import Any

from app.core.database import supabase, supabase_key, supabase_url

from app.modules.payslips.infrastructure.queries import (
    get_employee_statut as _get_employee_statut,
    get_payslip_meta as _get_payslip_meta,
)


class EmployeeStatutReader:
    """Implémentation de IEmployeeStatutReader (délègue à queries)."""

    def get_employee_statut(self, employee_id: str) -> str | None:
        return _get_employee_statut(employee_id)


class PayslipMetaReader:
    """Implémentation de IPayslipMetaReader (délègue à queries)."""

    def get_payslip_meta(self, payslip_id: str) -> dict[str, Any] | None:
        return _get_payslip_meta(payslip_id)


class DebugStorageInfoProvider:
    """Implémentation de IDebugStorageInfoProvider : métadonnées Storage pour diagnostic."""

    def get_debug_storage_info(
        self,
        employee_id: str,
        year: int,
        month: int,
    ) -> dict[str, Any]:
        emp = (
            supabase.table("employees")
            .select("company_id, employee_folder_name")
            .eq("id", employee_id)
            .single()
            .execute()
        )
        if not emp.data:
            raise ValueError("Employé non trouvé.")
        company_id = emp.data["company_id"]
        folder_name = emp.data["employee_folder_name"]
        storage_path = (
            f"{company_id}/{employee_id}/bulletins/"
            f"Bulletin_{folder_name}_{month:02d}-{year}.pdf"
        )
        file_url = f"{supabase_url}/storage/v1/object/info/payslips/{storage_path}"
        headers = {"apikey": supabase_key, "Authorization": f"Bearer {supabase_key}"}
        response = requests.get(file_url, headers=headers)
        return response.json()


employee_statut_reader = EmployeeStatutReader()
payslip_meta_reader = PayslipMetaReader()
debug_storage_info_provider = DebugStorageInfoProvider()
