# app/modules/medical_follow_up/infrastructure/repository.py
"""
Repository des obligations : implémentation de IObligationRepository.

Utilise infrastructure.queries pour la DB et domain.rules pour le calcul des KPIs.
Comportement identique au legacy.
"""

from datetime import date
from typing import Any, Dict, List, Optional

from app.modules.medical_follow_up.domain.interfaces import IObligationRepository
from app.modules.medical_follow_up.domain.rules import compute_kpis_from_rows
from app.modules.medical_follow_up.infrastructure import queries as infra_queries


class MedicalObligationRepository(IObligationRepository):
    """Implémentation du port IObligationRepository (Supabase)."""

    def __init__(self, supabase: Any):
        self._supabase = supabase

    def list_for_company(
        self,
        company_id: str,
        employee_id: Optional[str] = None,
        visit_type: Optional[str] = None,
        status: Optional[str] = None,
        priority: Optional[int] = None,
        due_from: Optional[str] = None,
        due_to: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        rows = infra_queries.list_obligations_raw(
            self._supabase,
            company_id,
            employee_id=employee_id,
            visit_type=visit_type,
            status=status,
            priority=priority,
            due_from=due_from,
            due_to=due_to,
            with_employee_join=True,
        )
        return rows

    def get_kpis(self, company_id: str) -> Dict[str, int]:
        rows = infra_queries.get_obligations_rows_for_kpis(self._supabase, company_id)
        return compute_kpis_from_rows(rows, date.today())

    def mark_planified(
        self,
        obligation_id: str,
        company_id: str,
        planned_date: str,
        justification: Optional[str],
    ) -> None:
        infra_queries.update_obligation_planified(
            self._supabase, obligation_id, planned_date, justification
        )

    def mark_completed(
        self,
        obligation_id: str,
        company_id: str,
        completed_date: str,
        justification: Optional[str],
    ) -> None:
        infra_queries.update_obligation_completed(
            self._supabase, obligation_id, completed_date, justification
        )

    def obligation_exists(self, obligation_id: str, company_id: str) -> bool:
        """True si l’obligation existe pour cette entreprise (pour lever 404 côté application)."""
        return infra_queries.get_obligation_by_id(self._supabase, obligation_id, company_id) is not None

    def create_on_demand(
        self,
        company_id: str,
        employee_id: str,
        request_motif: str,
        request_date: str,
    ) -> None:
        payload = {
            "company_id": company_id,
            "employee_id": employee_id,
            "visit_type": "demande",
            "trigger_type": "demande",
            "due_date": request_date,
            "priority": 3,
            "status": "a_faire",
            "rule_source": "legal",
            "request_motif": request_motif,
            "request_date": request_date,
        }
        infra_queries.insert_obligation(self._supabase, payload)

    def list_for_employee(self, company_id: str, employee_id: str) -> List[Dict[str, Any]]:
        return infra_queries.list_obligations_raw(
            self._supabase,
            company_id,
            employee_id=employee_id,
            with_employee_join=True,
        )

    def list_for_employee_no_join(self, company_id: str, employee_id: str) -> List[Dict[str, Any]]:
        """Liste obligations d’un employé sans join employee (pour /me)."""
        return infra_queries.list_obligations_raw(
            self._supabase,
            company_id,
            employee_id=employee_id,
            with_employee_join=False,
        )

    # Méthodes de lookup employé (hors interface, utilisées par l’application)

    def employee_exists(self, employee_id: str, company_id: str) -> bool:
        return infra_queries.get_employee_by_id(self._supabase, employee_id, company_id) is not None

    def get_employee_id_by_user_id(self, user_id: str, company_id: str) -> Optional[str]:
        return infra_queries.get_employee_id_by_user_id(self._supabase, user_id, company_id)
