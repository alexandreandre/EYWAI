"""
Commandes applicatives annual_reviews.

Orchestration : repository (infrastructure) + règles métier (domain).
Comportement strictement identique au legacy.
"""

from datetime import date, datetime
from typing import Any, Dict, Optional

from app.modules.annual_reviews.domain import rules as domain_rules
from app.modules.annual_reviews.domain.interfaces import IAnnualReviewRepository


def _serialize_date(value: Any) -> Any:
    """Retourne une date en isoformat si possible, sinon la valeur telle quelle."""
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def create_annual_review(
    company_id: str,
    data: Dict[str, Any],
    repository: IAnnualReviewRepository,
) -> Dict[str, Any]:
    """Crée un entretien. RH uniquement. Retourne la ligne créée."""
    employee_id = data.get("employee_id")
    if not employee_id:
        raise ValueError("employee_id requis")
    emp_company_id = repository.get_employee_company_id(employee_id)
    if not emp_company_id or emp_company_id != company_id:
        raise LookupError("Employé non trouvé.")

    planned_date = data.get("planned_date")
    insert_data = {
        "employee_id": employee_id,
        "company_id": company_id,
        "year": data["year"],
        "status": domain_rules.DEFAULT_STATUS_ON_CREATE,
        "planned_date": _serialize_date(planned_date),
        "rh_preparation_template": data.get("rh_preparation_template"),
    }
    return repository.create(insert_data)


def update_annual_review(
    review_id: str,
    company_id: str,
    current_user_id: str,
    is_rh: bool,
    data: Dict[str, Any],
    repository: IAnnualReviewRepository,
) -> Optional[Dict[str, Any]]:
    """Met à jour un entretien (RH ou employé selon champs autorisés)."""
    row = repository.get_by_id(review_id)
    if not row:
        raise LookupError("Entretien non trouvé.")
    if row["company_id"] != company_id:
        raise LookupError("Entretien non trouvé.")

    if not is_rh:
        if row["employee_id"] != current_user_id:
            raise PermissionError("Accès non autorisé.")
        update_data = domain_rules.build_employee_update_data(row["status"], data)
        if "employee_acceptance_status" in update_data:
            update_data["employee_acceptance_date"] = datetime.utcnow().isoformat()
    else:
        data_serialized = {
            k: _serialize_date(v)
            if k in ("planned_date", "completed_date", "next_review_date")
            else v
            for k, v in data.items()
        }
        update_data = domain_rules.build_rh_update_data(row["status"], data_serialized)

    if not update_data:
        return row

    updated = repository.update(review_id, update_data)
    return updated if updated is not None else row


def mark_completed(
    review_id: str,
    company_id: str,
    repository: IAnnualReviewRepository,
) -> Dict[str, Any]:
    """Marque l'entretien comme réalisé (status accepte -> realise). RH uniquement."""
    row = repository.get_by_id(review_id)
    if not row:
        raise LookupError("Entretien non trouvé.")
    if row["company_id"] != company_id:
        raise LookupError("Entretien non trouvé.")
    domain_rules.validate_can_mark_completed(row["status"])

    update_data = {
        "status": "realise",
        "completed_date": date.today().isoformat(),
    }
    updated = repository.update(review_id, update_data)
    if not updated:
        raise RuntimeError("Erreur lors de la mise à jour.")
    if "created_at" not in updated or "updated_at" not in updated:
        raise RuntimeError(
            f"Champs manquants dans la réponse: created_at={updated.get('created_at')}, updated_at={updated.get('updated_at')}"
        )
    return updated


def delete_annual_review(
    review_id: str,
    company_id: str,
    repository: IAnnualReviewRepository,
) -> None:
    """Supprime un entretien. RH uniquement."""
    row = repository.get_by_id(review_id)
    if not row:
        raise LookupError("Entretien non trouvé.")
    if row["company_id"] != company_id:
        raise LookupError("Entretien non trouvé.")
    repository.delete(review_id)
