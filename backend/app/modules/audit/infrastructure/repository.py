import logging
from typing import Any, Dict, List, Optional

from app.core.database import supabase

_log = logging.getLogger(__name__)

ACTIONS_LABELS = {
    "employee.create": "Création salarié",
    "employee.update": "Modification salarié",
    "employee.delete": "Suppression salarié",
    "payslip.validate": "Validation bulletin",
    "payslip.generate": "Génération bulletin",
    "absence.validate": "Validation absence",
    "absence.reject": "Refus absence",
    "document.sign": "Signature document",
    "salary.update": "Modification salaire",
    "recruitment.hire": "Embauche candidat",
    "user.create": "Création utilisateur",
    "user.update": "Modification utilisateur",
    "user.role_change": "Changement de rôle",
    "company.create": "Création entreprise",
    "company.update": "Modification entreprise",
    "access.permission_change": "Modification des droits",
    "support.ticket_status_change": "Mise à jour ticket support",
    "collective_agreement.assign": "Attribution convention collective",
}


class AuditRepository:
    def log(
        self,
        company_id: str,
        user_id: Optional[str],
        user_email: Optional[str],
        action: str,
        resource_type: str,
        resource_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
    ) -> None:
        """Best effort — ne jamais lever d'exception."""
        try:
            supabase.table("audit_logs").insert(
                {
                    "company_id": company_id,
                    "user_id": user_id,
                    "user_email": user_email,
                    "action": action,
                    "resource_type": resource_type,
                    "resource_id": resource_id,
                    "details": details,
                    "ip_address": ip_address,
                }
            ).execute()
        except Exception as e:
            _log.info("[audit] Non loggué: %s", e)

    def list_logs(
        self,
        company_id: str,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        user_id: Optional[str] = None,
        created_after: Optional[str] = None,
        created_before: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        Liste les entrées d'audit pour une entreprise, filtres optionnels,
        tri décroissant sur created_at.
        """
        try:
            q = supabase.table("audit_logs").select("*").eq("company_id", company_id)
            if resource_type:
                q = q.eq("resource_type", resource_type)
            if resource_id:
                q = q.eq("resource_id", resource_id)
            if user_id:
                q = q.eq("user_id", user_id)
            if created_after:
                q = q.gte("created_at", created_after)
            if created_before:
                q = q.lte("created_at", created_before)
            end = max(offset + limit - 1, offset)
            r = (
                q.order("created_at", desc=True)
                .range(offset, end)
                .execute()
            )
            return list(r.data or [])
        except Exception as e:
            _log.warning("[audit] list_logs échoué: %s", e)
            return []

    def list_logs_platform(
        self,
        company_id: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        user_id: Optional[str] = None,
        action: Optional[str] = None,
        created_after: Optional[str] = None,
        created_before: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Journal d'audit plateforme (super admin), avec nom d'entreprise si possible."""
        try:
            q = supabase.table("audit_logs").select("*")
            if company_id:
                q = q.eq("company_id", company_id)
            if resource_type:
                q = q.eq("resource_type", resource_type)
            if resource_id:
                q = q.eq("resource_id", resource_id)
            if user_id:
                q = q.eq("user_id", user_id)
            if action:
                q = q.eq("action", action)
            if created_after:
                q = q.gte("created_at", created_after)
            if created_before:
                q = q.lte("created_at", created_before)
            end = max(offset + limit - 1, offset)
            r = (
                q.order("created_at", desc=True)
                .range(offset, end)
                .execute()
            )
            rows = list(r.data or [])
            if not rows:
                return []
            company_ids = {str(row["company_id"]) for row in rows if row.get("company_id")}
            names: Dict[str, str] = {}
            if company_ids:
                cr = (
                    supabase.table("companies")
                    .select("id, company_name")
                    .in_("id", list(company_ids))
                    .execute()
                )
                for c in cr.data or []:
                    names[str(c["id"])] = c.get("company_name") or ""
            for row in rows:
                cid = str(row.get("company_id") or "")
                row["company_name"] = names.get(cid)
            return rows
        except Exception as e:
            _log.warning("[audit] list_logs_platform échoué: %s", e)
            return []


audit_repository = AuditRepository()
