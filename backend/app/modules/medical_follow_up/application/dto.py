# app/modules/medical_follow_up/application/dto.py
"""DTOs du module suivi médical (structure cible pour la couche application)."""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class ObligationListDTO:
    """Une obligation pour la liste (aligné ObligationListItem)."""

    id: str
    company_id: str
    employee_id: str
    visit_type: str
    trigger_type: str
    due_date: str
    priority: int
    status: str
    rule_source: str
    justification: Optional[str] = None
    planned_date: Optional[str] = None
    completed_date: Optional[str] = None
    collective_agreement_idcc: Optional[str] = None
    request_motif: Optional[str] = None
    request_date: Optional[str] = None
    employee_first_name: Optional[str] = None
    employee_last_name: Optional[str] = None

    @classmethod
    def from_row(cls, r: Dict[str, Any]) -> "ObligationListDTO":
        """Construit depuis une ligne DB (avec join employee optionnel)."""
        emp = r.get("employee") or {}
        return cls(
            id=r["id"],
            company_id=r["company_id"],
            employee_id=r["employee_id"],
            visit_type=r["visit_type"],
            trigger_type=r["trigger_type"],
            due_date=r["due_date"],
            priority=r["priority"],
            status=r["status"],
            rule_source=r.get("rule_source") or "legal",
            justification=r.get("justification"),
            planned_date=r.get("planned_date"),
            completed_date=r.get("completed_date"),
            collective_agreement_idcc=r.get("collective_agreement_idcc"),
            request_motif=r.get("request_motif"),
            request_date=r.get("request_date"),
            employee_first_name=emp.get("first_name"),
            employee_last_name=emp.get("last_name"),
        )


@dataclass
class KPIsDTO:
    """Indicateurs KPIs (aligné KPIsResponse)."""

    overdue_count: int
    due_within_30_count: int
    active_total: int
    completed_this_month: int
