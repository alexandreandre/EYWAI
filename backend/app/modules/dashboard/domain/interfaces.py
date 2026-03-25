"""
Ports (interfaces) du domaine dashboard.

L'application dépend de ces abstractions ; l'infrastructure les implémente.
Aucune dépendance à Supabase ou FastAPI.
"""

from __future__ import annotations

from typing import Any, List, Protocol


class IResidencePermitStatusCalculator(Protocol):
    """
    Calcule le statut d'un titre de séjour (ex. valid, to_renew, expired, to_complete).
    Implémentation actuelle : services.residence_permit_service.ResidencePermitService.
    """

    def calculate_residence_permit_status(
        self,
        is_subject_to_residence_permit: bool,
        residence_permit_expiry_date: Any,
        employment_status: str,
        reference_date: Any = None,
    ) -> dict: ...


class IDashboardDataReader(Protocol):
    """
    Lit les données brutes nécessaires à l'agrégation dashboard
    (employés, absences, paie, dépenses) pour une company_id.
    Implémentation : infrastructure.queries / repository.
    """

    def get_employees_for_dashboard(self, company_id: str) -> List[dict]: ...

    def get_absence_requests_validated_today(self, company_id: str) -> List[dict]: ...

    def get_absence_requests_for_absenteeism(self, company_id: str) -> List[dict]: ...

    def get_payslips_by_company(self, company_id: str) -> List[dict]: ...

    def get_pending_expense_reports_count(self, company_id: str) -> int: ...

    def get_pending_absence_requests_count(self, company_id: str) -> int: ...

    def get_employees_for_residence_permit_stats(self, company_id: str) -> List[dict]:
        """Employés soumis au titre de séjour (actif/en_sortie) pour calcul des stats."""
        ...
