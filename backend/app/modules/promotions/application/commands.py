"""
Commandes (cas d'usage écriture) du module promotions.

Orchestration : domain rules + repository + employee updater. Aucune logique DB directe.
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Optional

from fastapi import HTTPException

from app.modules.promotions.application.queries import get_promotion_by_id_query
from app.modules.promotions.application.service import apply_promotion_changes
from app.modules.promotions.domain.rules import validate_rh_access_transition
from app.modules.promotions.infrastructure.providers import (
    get_promotion_document_provider,
)
from app.modules.promotions.infrastructure.queries import (
    get_employee_snapshot_for_promotion,
)
from app.modules.promotions.infrastructure.repository import get_promotion_repository
from app.modules.promotions.schemas import (
    PromotionCreate,
    PromotionRead,
    PromotionUpdate,
)

logger = logging.getLogger(__name__)


def create_promotion_cmd(
    body: PromotionCreate,
    company_id: str,
    requested_by: str,
) -> PromotionRead:
    """Crée une nouvelle promotion (snapshot employé via infra, statut initial, optionnellement effective)."""
    try:
        snapshot = get_employee_snapshot_for_promotion(body.employee_id, company_id)
        employee = snapshot["employee"]
        previous_rh_access = snapshot["previous_rh_access"]

        if body.grant_rh_access and body.new_rh_access:
            if not validate_rh_access_transition(
                previous_rh_access, body.new_rh_access
            ):
                raise HTTPException(
                    status_code=400,
                    detail=f"Transition de rôle RH non autorisée: {previous_rh_access} → {body.new_rh_access}",
                )

        today = date.today()
        initial_status = "effective" if body.effective_date <= today else "draft"
        insert_data = {
            "company_id": company_id,
            "employee_id": body.employee_id,
            "promotion_type": body.promotion_type,
            "previous_job_title": employee.get("job_title"),
            "previous_salary": employee.get("salaire_de_base"),
            "previous_statut": employee.get("statut"),
            "previous_classification": employee.get("classification_conventionnelle"),
            "previous_rh_access": previous_rh_access,
            "new_job_title": body.new_job_title,
            "new_salary": body.new_salary,
            "new_statut": body.new_statut,
            "new_classification": body.new_classification,
            "new_rh_access": body.new_rh_access,
            "grant_rh_access": body.grant_rh_access,
            "effective_date": body.effective_date.isoformat(),
            "request_date": body.request_date.isoformat(),
            "status": initial_status,
            "reason": body.reason,
            "justification": body.justification,
            "performance_review_id": body.performance_review_id,
            "requested_by": requested_by,
            "approved_by": requested_by if initial_status == "effective" else None,
            "approved_at": datetime.now().isoformat()
            if initial_status == "effective"
            else None,
        }
        repo = get_promotion_repository()
        created_promotion_id = repo.create(insert_data, company_id, requested_by)
        if initial_status == "effective":
            created_promotion = get_promotion_by_id_query(
                created_promotion_id, company_id
            )
            apply_promotion_changes(created_promotion, company_id)
        return get_promotion_by_id_query(created_promotion_id, company_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erreur lors de la création de la promotion: {str(e)}",
        )


def update_promotion_cmd(
    promotion_id: str,
    body: PromotionUpdate,
    company_id: str,
) -> PromotionRead:
    """Met à jour une promotion (uniquement en statut draft)."""
    try:
        repo = get_promotion_repository()
        current_promo = repo.get_by_id(promotion_id, company_id)
        if current_promo is None:
            raise HTTPException(status_code=404, detail="Promotion non trouvée")
        if current_promo.status != "draft":
            raise HTTPException(
                status_code=400,
                detail=f"Impossible de modifier une promotion en statut '{current_promo.status}'",
            )
        if body.grant_rh_access is True and body.new_rh_access:
            if not validate_rh_access_transition(
                current_promo.previous_rh_access, body.new_rh_access
            ):
                raise HTTPException(
                    status_code=400,
                    detail=f"Transition de rôle RH non autorisée: {current_promo.previous_rh_access} → {body.new_rh_access}",
                )
        update_data = {}
        if body.promotion_type is not None:
            update_data["promotion_type"] = body.promotion_type
        if body.new_job_title is not None:
            update_data["new_job_title"] = body.new_job_title
        if body.new_salary is not None:
            update_data["new_salary"] = body.new_salary
        if body.new_statut is not None:
            update_data["new_statut"] = body.new_statut
        if body.new_classification is not None:
            update_data["new_classification"] = body.new_classification
        if body.effective_date is not None:
            update_data["effective_date"] = body.effective_date.isoformat()
        if body.reason is not None:
            update_data["reason"] = body.reason
        if body.justification is not None:
            update_data["justification"] = body.justification
        if body.performance_review_id is not None:
            update_data["performance_review_id"] = body.performance_review_id
        if body.grant_rh_access is not None:
            update_data["grant_rh_access"] = body.grant_rh_access
        if body.new_rh_access is not None:
            update_data["new_rh_access"] = body.new_rh_access
        if update_data:
            repo.update(promotion_id, company_id, update_data)
        return get_promotion_by_id_query(promotion_id, company_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erreur lors de la mise à jour de la promotion: {str(e)}",
        )


def submit_promotion_cmd(promotion_id: str, company_id: str) -> PromotionRead:
    """Soumet une promotion (draft → pending_approval)."""
    try:
        repo = get_promotion_repository()
        current_promo = repo.get_by_id(promotion_id, company_id)
        if current_promo is None:
            raise HTTPException(status_code=404, detail="Promotion non trouvée")
        if current_promo.status != "draft":
            raise HTTPException(
                status_code=400,
                detail=f"Impossible de soumettre une promotion en statut '{current_promo.status}'",
            )
        if not any(
            [
                current_promo.new_job_title,
                current_promo.new_salary,
                current_promo.new_statut,
                current_promo.new_classification,
            ]
        ):
            raise HTTPException(
                status_code=400,
                detail="Au moins un champ 'nouveau' doit être renseigné avant de soumettre",
            )
        repo.update(promotion_id, company_id, {"status": "pending_approval"})
        return get_promotion_by_id_query(promotion_id, company_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erreur lors de la soumission de la promotion: {str(e)}",
        )


def approve_promotion_cmd(
    promotion_id: str,
    company_id: str,
    approved_by: str,
    notes: Optional[str] = None,
) -> PromotionRead:
    """Approuve une promotion (pending_approval → approved), génère le PDF via provider."""
    try:
        repo = get_promotion_repository()
        current_promo = repo.get_by_id(promotion_id, company_id)
        if current_promo is None:
            raise HTTPException(status_code=404, detail="Promotion non trouvée")
        if current_promo.status != "pending_approval":
            raise HTTPException(
                status_code=400,
                detail=f"Impossible d'approuver une promotion en statut '{current_promo.status}'",
            )
        update_data = {
            "status": "approved",
            "approved_by": approved_by,
            "approved_at": datetime.now().isoformat(),
        }
        if notes:
            current_notes = current_promo.notes or []
            if not isinstance(current_notes, list):
                current_notes = []
            current_notes.append(
                {
                    "author_id": approved_by,
                    "timestamp": datetime.now().isoformat(),
                    "content": notes,
                    "type": "approval_note",
                }
            )
            update_data["notes"] = current_notes
        repo.update(promotion_id, company_id, update_data)
        try:
            from app.modules.promotions.infrastructure.queries import (
                get_company_data_for_document,
                get_employee_data_for_document,
            )

            employee_data = get_employee_data_for_document(current_promo.employee_id)
            company_data = get_company_data_for_document(company_id)
            promotion_dict = (
                current_promo.model_dump()
                if hasattr(current_promo, "model_dump")
                else dict(current_promo)
            )
            provider = get_promotion_document_provider()
            pdf_bytes = provider.generate_letter(
                promotion_data=promotion_dict,
                employee_data=employee_data,
                company_data=company_data,
            )
            pdf_url = provider.save_document(
                promotion_id=promotion_id,
                company_id=company_id,
                employee_id=current_promo.employee_id,
                employee_folder_name=employee_data.get("employee_folder_name", ""),
                pdf_bytes=pdf_bytes,
            )
            repo.update(promotion_id, company_id, {"promotion_letter_url": pdf_url})
        except Exception as pdf_error:
            logger.error(
                "Erreur lors de la génération du PDF de promotion %s: %s",
                promotion_id,
                pdf_error,
            )
        return get_promotion_by_id_query(promotion_id, company_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erreur lors de l'approbation de la promotion: {str(e)}",
        )


def reject_promotion_cmd(
    promotion_id: str,
    company_id: str,
    rejection_reason: str,
) -> PromotionRead:
    """Rejette une promotion (pending_approval → rejected)."""
    try:
        repo = get_promotion_repository()
        current_promo = repo.get_by_id(promotion_id, company_id)
        if current_promo is None:
            raise HTTPException(status_code=404, detail="Promotion non trouvée")
        if current_promo.status != "pending_approval":
            raise HTTPException(
                status_code=400,
                detail=f"Impossible de rejeter une promotion en statut '{current_promo.status}'",
            )
        repo.update(
            promotion_id,
            company_id,
            {"status": "rejected", "rejection_reason": rejection_reason},
        )
        return get_promotion_by_id_query(promotion_id, company_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erreur lors du rejet de la promotion: {str(e)}",
        )


def mark_effective_promotion_cmd(promotion_id: str, company_id: str) -> PromotionRead:
    """Marque une promotion comme effective et applique les changements (délègue à IEmployeeUpdater)."""
    try:
        current_promo = get_promotion_by_id_query(promotion_id, company_id)
        if current_promo.status not in ("draft", "effective"):
            raise HTTPException(
                status_code=400,
                detail=f"Impossible de marquer comme effective une promotion en statut '{current_promo.status}'. Seules les promotions en 'draft' peuvent être marquées comme effective.",
            )
        if current_promo.status == "effective":
            return current_promo
        apply_promotion_changes(current_promo, company_id)
        repo = get_promotion_repository()
        update_data = {"status": "effective"}
        if not current_promo.approved_by:
            update_data["approved_by"] = current_promo.requested_by
            update_data["approved_at"] = datetime.now().isoformat()
        repo.update(promotion_id, company_id, update_data)
        return get_promotion_by_id_query(promotion_id, company_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erreur lors de la mise à jour de la promotion: {str(e)}",
        )


def delete_promotion_cmd(promotion_id: str, company_id: str) -> None:
    """Supprime une promotion (uniquement en statut draft)."""
    try:
        repo = get_promotion_repository()
        current_promo = repo.get_by_id(promotion_id, company_id)
        if current_promo is None:
            raise HTTPException(status_code=404, detail="Promotion non trouvée")
        if current_promo.status != "draft":
            raise HTTPException(
                status_code=400,
                detail=f"Impossible de supprimer une promotion en statut '{current_promo.status}'",
            )
        repo.delete(promotion_id, company_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erreur lors de la suppression de la promotion: {str(e)}",
        )


__all__ = [
    "create_promotion_cmd",
    "update_promotion_cmd",
    "submit_promotion_cmd",
    "approve_promotion_cmd",
    "reject_promotion_cmd",
    "mark_effective_promotion_cmd",
    "delete_promotion_cmd",
]
