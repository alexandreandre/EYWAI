"""
Repository absences — implémentation IAbsenceRepository.

Accès table absence_requests via Supabase. Comportement identique à l'ancien routeur.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.core.database import supabase

from app.modules.absences.domain.interfaces import IAbsenceRepository
from app.modules.absences.infrastructure.short_cache import ShortLivedCache

logger = logging.getLogger(__name__)

# Le calcul des soldes est appelé plusieurs fois par salarié sur les écrans de
# campagne : sans mutualisation, le planning est relu à chaque fois.
_planning_cache = ShortLivedCache()
_cutoff_cache = ShortLivedCache()


def _with_planning_conges_payes(
    validated: List[Dict[str, Any]], employee_ids: List[str]
) -> List[Dict[str, Any]]:
    """
    Complète les demandes validées par les congés payés saisis au planning.

    Les congés payés ne sont pas posés en demande d'absence : sans cette
    lecture, les compteurs ne se décrémenteraient jamais. Un échec ici ne doit
    pas empêcher l'affichage d'un solde — on retombe sur les seules demandes.
    """
    from app.modules.absences.domain.planning_cp import merge_planning_cp_days
    from app.modules.absences.infrastructure import planning_cp_repository

    try:
        cle = tuple(sorted(employee_ids))
        planning = _planning_cache.get_or_load(
            cle, lambda ids: planning_cp_repository.list_planning_cp_days(list(ids))
        )
        if not planning:
            return validated
        cutoffs = _cutoff_cache.get_or_load(
            cle,
            lambda ids: planning_cp_repository.get_cp_opening_reference_dates(
                list(ids)
            ),
        )
        return merge_planning_cp_days(validated, planning, cutoffs)
    except Exception:
        logger.warning(
            "Congés payés du planning ignorés pour le calcul des soldes",
            exc_info=True,
        )
        return validated


class SupabaseAbsenceRepository(IAbsenceRepository):
    """Implémentation Supabase pour absence_requests."""

    @staticmethod
    def _resolve_employee_id_for_user(
        user_id: str, company_id: str
    ) -> Optional[str]:
        from app.shared.employee_resolution import (
            resolve_employee_id_for_user_account,
        )

        return resolve_employee_id_for_user_account(str(user_id), str(company_id))

    def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        response = supabase.table("absence_requests").insert(data).execute()
        if not response.data:
            raise RuntimeError("Échec de la création de la demande.")
        return response.data[0]

    def get_by_id(self, request_id: str) -> Optional[Dict[str, Any]]:
        r = (
            supabase.table("absence_requests")
            .select("*")
            .eq("id", request_id)
            .maybe_single()
            .execute()
        )
        return r.data if r.data else None

    def update(self, request_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        update_resp = (
            supabase.table("absence_requests")
            .update(data)
            .eq("id", request_id)
            .execute()
        )
        if not update_resp.data:
            return None
        r = (
            supabase.table("absence_requests")
            .select("*")
            .eq("id", request_id)
            .single()
            .execute()
        )
        return r.data if r.data else None

    def list_by_status(
        self, status: Optional[str], company_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        query = supabase.table("absence_requests").select(
            "*, employee:employees(id, first_name, last_name)"
        )
        if company_id:
            query = query.eq("company_id", company_id)
        if status:
            query = query.eq("status", status)
            # Les demandes encore chez le manager ne sont pas visibles dans la file RH « pending ».
            if status == "pending":
                query = query.neq("workflow_step", "pending_manager")
        result = query.order("created_at", desc=True).execute()
        return result.data or []

    def get_team_manager_employee_id_for_employee(
        self, employee_id: str
    ) -> Optional[str]:
        """Retourne l'employee_id du manager d'équipe (teams.manager_employee_id) si défini."""
        from app.shared.team_manager import get_team_manager_employee_id

        return get_team_manager_employee_id(employee_id)

    def get_pending_manager_approval(self, company_id: str) -> List[Dict[str, Any]]:
        """
        SELECT absence_requests WHERE company_id
        AND workflow_step = 'pending_manager'
        AND status = 'pending'
        Pattern liste EYWAI (join employé).
        """
        result = (
            supabase.table("absence_requests")
            .select("*, employee:employees(id, first_name, last_name)")
            .eq("company_id", company_id)
            .eq("workflow_step", "pending_manager")
            .eq("status", "pending")
            .order("created_at", desc=True)
            .execute()
        )
        return result.data or []

    def get_employee_ids_managed_by_manager(
        self, manager_employee_id: str, company_id: str
    ) -> List[str]:
        """IDs des employés dont l'équipe a ce manager (teams actives de l'entreprise)."""
        from app.shared.team_manager import get_employee_ids_managed_by_manager

        return get_employee_ids_managed_by_manager(manager_employee_id, company_id)

    def approve_by_manager(
        self,
        absence_id: str,
        company_id: str,
        manager_user_id: str,
        approved: bool,
        rejection_reason: str | None,
    ) -> Dict[str, Any]:
        """
        UPDATE absence_requests :
        Si approved : workflow_step = approved_manager, manager_approved_at = now(), manager_id = résolu.
        Sinon : workflow_step = rejected_manager, status = rejected, manager_rejected_at, motif.
        """
        row = self.get_by_id(absence_id)
        if not row:
            raise LookupError(f"Demande {absence_id} introuvable.")
        if str(row.get("company_id") or "") != str(company_id):
            raise LookupError("Demande introuvable pour cette entreprise.")
        if row.get("status") != "pending" or row.get("workflow_step") != "pending_manager":
            raise ValueError(
                "Cette demande n'est pas en attente de validation manager."
            )

        now_iso = datetime.now(timezone.utc).isoformat()

        manager_employee_id = self._resolve_employee_id_for_user(
            manager_user_id, str(company_id)
        )

        if approved:
            update_payload: Dict[str, Any] = {
                "workflow_step": "approved_manager",
                "manager_approved_at": now_iso,
            }
            if manager_employee_id:
                update_payload["manager_id"] = manager_employee_id
            updated = self.update(absence_id, update_payload)
        else:
            update_payload = {
                "workflow_step": "rejected_manager",
                "status": "rejected",
                "manager_rejected_at": now_iso,
                "manager_rejection_reason": rejection_reason,
            }
            if manager_employee_id:
                update_payload["manager_id"] = manager_employee_id
            updated = self.update(absence_id, update_payload)
        if not updated:
            raise RuntimeError("Échec de la mise à jour de la demande.")
        return updated

    def list_validated_for_employees(
        self, employee_ids: List[str]
    ) -> List[Dict[str, Any]]:
        if not employee_ids:
            return []
        result = (
            supabase.table("absence_requests")
            .select("employee_id", "type", "selected_days", "jours_payes", "arret_type")
            .in_("employee_id", employee_ids)
            .eq("status", "validated")
            .execute()
        )
        validated = result.data or []
        for row in validated:
            row.setdefault("status", "validated")
        return _with_planning_conges_payes(validated, employee_ids)

    def list_by_employee_id(self, employee_id: str) -> List[Dict[str, Any]]:
        result = (
            supabase.table("absence_requests")
            .select("*")
            .eq("employee_id", employee_id)
            .order("created_at", desc=True)
            .execute()
        )
        return result.data if result.data is not None else []


absence_repository = SupabaseAbsenceRepository()
