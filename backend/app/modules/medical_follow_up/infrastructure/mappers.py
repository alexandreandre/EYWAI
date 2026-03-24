# app/modules/medical_follow_up/infrastructure/mappers.py
"""Mappers row -> domain / DTO (placeholder)."""

from typing import Any, Dict

from app.modules.medical_follow_up.domain.entities import MedicalObligation


def row_to_obligation_entity(row: Dict[str, Any]) -> MedicalObligation:
    """Mappe une ligne DB vers MedicalObligation. Placeholder ; à compléter avec les champs réels."""
    return MedicalObligation(
        id=row["id"],
        company_id=row["company_id"],
        employee_id=row["employee_id"],
        visit_type=row["visit_type"],
        trigger_type=row["trigger_type"],
        due_date=row["due_date"],
        priority=row["priority"],
        status=row["status"],
        rule_source=row.get("rule_source") or "legal",
        justification=row.get("justification"),
        planned_date=row.get("planned_date"),
        completed_date=row.get("completed_date"),
        collective_agreement_idcc=row.get("collective_agreement_idcc"),
        request_motif=row.get("request_motif"),
        request_date=row.get("request_date"),
    )
