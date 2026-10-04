"""
Repository payslips : accès table payslips + storage, suppression + recalc COR.

Wrapper prêt pour la migration ; utilise app.core.database.supabase.
Pour l'instant get_by_id / list_by_employee peuvent passer par les queries ;
delete réplique le comportement du router legacy (BDD + storage + recalc COR).
"""

from __future__ import annotations

from typing import Any

from app.core.constants import AUDIT_BULLETIN_SUPPRIME
from app.core.database import supabase
from app.modules.audit.infrastructure.repository import audit_repository
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
        return r.data if r else None

    def list_by_employee(self, employee_id: str) -> list[dict[str, Any]]:
        r = (
            supabase.table("payslips")
            .select("*")
            .eq("employee_id", employee_id)
            .order("year", desc=True)
            .order("month", desc=True)
            .execute()
        )
        return (r.data or []) if r else []

    def delete(self, payslip_id: str) -> bool:
        """Supprime le bulletin (BDD + storage) et déclenche recalc COR.

        Faux, sans rien toucher, si le bulletin n'existe plus : `.single()`
        levait sur la ligne absente et la suppression répondait 500.
        """
        r = (
            supabase.table("payslips")
            .select("pdf_storage_path, employee_id, company_id, year, month")
            .eq("id", payslip_id)
            .maybe_single()
            .execute()
        )
        row = r.data if r else None
        if not row:
            return False

        supabase.table("payslips").delete().eq("id", payslip_id).execute()

        if row.get("company_id"):
            # Un bulletin recalculé ou ajouté se date lui-même ; supprimé, il
            # n'est plus là pour le dire. La trace datée rend « à refaire » les
            # exports déjà faits pour son mois. Sans échec possible (best effort).
            audit_repository.log(
                str(row["company_id"]),
                None,
                None,
                AUDIT_BULLETIN_SUPPRIME,
                "payslip",
                resource_id=payslip_id,
                details={
                    "employee_id": row.get("employee_id"),
                    "year": row.get("year"),
                    "month": row.get("month"),
                },
            )

        if row.get("employee_id") and row.get("year") and row.get("month"):
            # Les cumuls du mois partent avec le bulletin : restés en base, ils
            # servaient de départ au mois suivant comme si ce bulletin avait été
            # payé. Effacés, un mois suivant déjà calculé passe « À recalculer »
            # (empreinte des cumuls), et le calcul suivant demande ce mois d'abord.
            try:
                supabase.table("employee_schedules").update({"cumuls": None}).match(
                    {
                        "employee_id": row["employee_id"],
                        "year": row["year"],
                        "month": row["month"],
                    }
                ).execute()
            except Exception as err:
                import warnings

                warnings.warn(
                    f"Cumuls du bulletin supprimé non effacés : {err}", stacklevel=2
                )

        if row.get("employee_id"):
            try:
                recalculer_credits_repos_employe(
                    row["employee_id"],
                    row["company_id"],
                    row["year"],
                )
            except Exception as err:
                import warnings

                warnings.warn(
                    f"Recalc COR après suppression bulletin: {err}", stacklevel=2
                )

        if row.get("pdf_storage_path"):
            supabase.storage.from_("payslips").remove([row["pdf_storage_path"]])
        return True


payslip_repository = PayslipRepository()
