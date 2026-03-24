"""
Règles métier pures annual_reviews.

Aucune dépendance FastAPI ni DB. Entrées/sorties : types primitifs et dicts.
Les dates sont reçues déjà sérialisées (str ou None) par la couche application.
"""
from typing import Any, Dict

# Statut requis pour marquer comme réalisé
STATUS_REQUIRED_FOR_MARK_COMPLETED = "accepte"

# Statut requis pour générer le PDF
STATUS_REQUIRED_FOR_PDF = "cloture"

# Statut initial à la création
DEFAULT_STATUS_ON_CREATE = "en_attente_acceptation"


def employee_can_update_acceptance(status: str) -> bool:
    """Employé peut accepter/refuser uniquement si en_attente_acceptation."""
    return status == "en_attente_acceptation"


def employee_can_update_preparation_notes(status: str) -> bool:
    """Employé peut modifier ses notes de préparation si accepte."""
    return status == "accepte"


def rh_can_edit_full_fiche(status: str) -> bool:
    """RH peut éditer la fiche complète (compte-rendu, etc.) si réalise ou clôture."""
    return status in ("realise", "cloture")


def build_employee_update_data(current_status: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Construit le payload de mise à jour autorisé pour un employé.
    data : dict avec clés déjà sérialisées (pas d'objets date).
    Lève ValueError si aucune modification autorisée.
    L'appelant doit ajouter employee_acceptance_date si acceptation/refus.
    """
    update_data: Dict[str, Any] = {}
    if current_status == "en_attente_acceptation":
        if data.get("employee_acceptance_status") is not None:
            update_data["employee_acceptance_status"] = data["employee_acceptance_status"]
            if data["employee_acceptance_status"] == "accepte":
                update_data["status"] = "accepte"
            elif data["employee_acceptance_status"] == "refuse":
                update_data["status"] = "refuse"
    if current_status == "accepte":
        if data.get("employee_preparation_notes") is not None:
            update_data["employee_preparation_notes"] = data["employee_preparation_notes"]
    if not update_data:
        raise ValueError(
            "Vous ne pouvez modifier que vos notes de préparation lorsque l'entretien est accepté, "
            "ou accepter/refuser lorsque l'entretien est en attente d'acceptation."
        )
    return update_data


def build_rh_update_data(current_status: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Construit le payload de mise à jour autorisé pour un RH.
    data : dict avec valeurs déjà sérialisées (dates en str iso ou None).
    """
    update_data: Dict[str, Any] = {}
    if data.get("planned_date") is not None:
        update_data["planned_date"] = data["planned_date"]
    if data.get("completed_date") is not None:
        update_data["completed_date"] = data["completed_date"]
    if data.get("status") is not None:
        update_data["status"] = data["status"]
    if data.get("rh_preparation_template") is not None:
        update_data["rh_preparation_template"] = data["rh_preparation_template"]
    if current_status in ("realise", "cloture"):
        if data.get("meeting_report") is not None:
            update_data["meeting_report"] = data["meeting_report"]
        if data.get("rh_notes") is not None:
            update_data["rh_notes"] = data["rh_notes"]
        if data.get("evaluation_summary") is not None:
            update_data["evaluation_summary"] = data["evaluation_summary"]
        if data.get("objectives_achieved") is not None:
            update_data["objectives_achieved"] = data["objectives_achieved"]
        if data.get("objectives_next_year") is not None:
            update_data["objectives_next_year"] = data["objectives_next_year"]
        if data.get("strengths") is not None:
            update_data["strengths"] = data["strengths"]
        if data.get("improvement_areas") is not None:
            update_data["improvement_areas"] = data["improvement_areas"]
        if data.get("training_needs") is not None:
            update_data["training_needs"] = data["training_needs"]
        if data.get("career_development") is not None:
            update_data["career_development"] = data["career_development"]
        if data.get("salary_review") is not None:
            update_data["salary_review"] = data["salary_review"]
        if data.get("overall_rating") is not None:
            update_data["overall_rating"] = data["overall_rating"]
        if data.get("next_review_date") is not None:
            update_data["next_review_date"] = data["next_review_date"]
    return update_data


def validate_can_mark_completed(current_status: str) -> None:
    """Lève ValueError si l'entretien ne peut pas être marqué comme réalisé."""
    if current_status != STATUS_REQUIRED_FOR_MARK_COMPLETED:
        raise ValueError(
            "L'entretien ne peut être marqué comme réalisé que lorsqu'il a été accepté par l'employé."
        )


def validate_pdf_allowed(current_status: str) -> None:
    """Lève ValueError si le PDF n'est pas autorisé (entretien non clôturé)."""
    if current_status != STATUS_REQUIRED_FOR_PDF:
        raise ValueError("Le PDF ne peut être généré que pour un entretien clôturé.")
