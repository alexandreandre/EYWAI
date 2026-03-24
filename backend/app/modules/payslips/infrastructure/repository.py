"""
Repository payslips : accès table payslips + storage, suppression + recalc COR.

Wrapper prêt pour la migration ; utilise app.core.database.supabase.
Pour l'instant get_by_id / list_by_employee peuvent passer par les queries ;
delete réplique le comportement du router legacy (BDD + storage + recalc COR).
"""
from __future__ import annotations

from typing import Any

from app.core.database import supabase
from app.shared.infrastructure.payslip_services import recalculer_credits_repos_employe


class PayslipRepository:
    """Accès écriture / lecture payslips (table + bucket payslips)."""

    def get_by_id(self, payslip_id: str) -> dict[str, Any] | None:
        r = (
            supabase.table("payslips")
            .select("*")
            .eq("id", payslip_id)
            .single()
            .execute()
        )
        return r.data if r.data else None

    def list_by_employee(self, employee_id: str) -> list[dict[str, Any]]:
        r = (
            supabase.table("payslips")
            .select("*")
            .eq("employee_id", employee_id)
            .order("year", desc=True)
            .order("month", desc=True)
            .execute()
        )
        return r.data or []

    def delete(self, payslip_id: str) -> None:
        """Supprime le bulletin (BDD + storage) et déclenche recalc COR."""
        row = (
            supabase.table("payslips")
            .select("pdf_storage_path, employee_id, company_id, year, month")
            .eq("id", payslip_id)
            .single()
            .execute()
            .data
        )

        supabase.table("payslips").delete().eq("id", payslip_id).execute()

        if row and row.get("employee_id"):
            try:
                recalculer_credits_repos_employe(
                    row["employee_id"],
                    row["company_id"],
                    row["year"],
                )
            except Exception as err:
                import warnings
                warnings.warn(f"Recalc COR après suppression bulletin: {err}", stacklevel=2)

        if row and row.get("pdf_storage_path"):
            supabase.storage.from_("payslips").remove([row["pdf_storage_path"]])


payslip_repository = PayslipRepository()
