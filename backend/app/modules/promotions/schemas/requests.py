"""
Schémas de requête API pour le module promotions.

Définitions canoniques (migrées depuis schemas.promotion). Comportement identique.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from app.modules.promotions.schemas.responses import PromotionType, RhAccessRole


class PromotionCreate(BaseModel):
    """
    Schéma pour la création d'une promotion.

    Exemple:
    ```python
    {
        "employee_id": "123e4567-e89b-12d3-a456-426614174000",
        "promotion_type": "salaire",
        "new_salary": {"valeur": 3500, "devise": "EUR"},
        "effective_date": "2026-03-01",
        "reason": "Performance exceptionnelle",
        "grant_rh_access": True,
        "new_rh_access": "collaborateur_rh"
    }
    ```
    """

    employee_id: str = Field(..., description="ID de l'employé concerné par la promotion")
    promotion_type: PromotionType = Field(..., description="Type de promotion")
    new_job_title: Optional[str] = Field(None, description="Nouveau poste (si changement de poste)")
    new_salary: Optional[Dict[str, Any]] = Field(None, description="Nouveau salaire au format JSONB")
    new_statut: Optional[str] = Field(None, description="Nouveau statut (Cadre/Non-Cadre)")
    new_classification: Optional[Dict[str, Any]] = Field(
        None, description="Nouvelle classification conventionnelle"
    )
    effective_date: date = Field(..., description="Date d'effet de la promotion")
    request_date: date = Field(
        default_factory=date.today,
        description="Date de la demande (par défaut aujourd'hui)",
    )
    reason: Optional[str] = Field(None, description="Raison de la promotion")
    justification: Optional[str] = Field(None, description="Justification détaillée")
    performance_review_id: Optional[str] = Field(
        None, description="ID de l'entretien annuel associé"
    )
    status: Literal["draft", "effective"] = Field(
        "draft",
        description="Statut initial: draft (brouillon) ou effective (effective immédiatement si date d'effet <= aujourd'hui)",
    )
    grant_rh_access: bool = Field(
        False,
        description="Indique si des accès RH doivent être donnés lors de la promotion effective",
    )
    new_rh_access: Optional[RhAccessRole] = Field(
        None,
        description="Nouveau rôle RH à attribuer (collaborateur_rh, rh, admin)",
    )

    @model_validator(mode="after")
    def validate_promotion_data(self):
        """Valide que au moins un champ 'nouveau' est renseigné."""
        has_new_data = any([
            self.new_job_title is not None,
            self.new_salary is not None,
            self.new_statut is not None,
            self.new_classification is not None,
        ])
        if not has_new_data:
            raise ValueError(
                "Au moins un champ 'nouveau' doit être renseigné "
                "(new_job_title, new_salary, new_statut, ou new_classification)"
            )
        return self

    @model_validator(mode="after")
    def validate_rh_access(self):
        """Valide que si grant_rh_access = True, alors new_rh_access doit être renseigné."""
        if self.grant_rh_access and self.new_rh_access is None:
            raise ValueError(
                "Si grant_rh_access est True, new_rh_access doit être renseigné "
                "(collaborateur_rh, rh, ou admin)"
            )
        return self

    @field_validator("effective_date")
    @classmethod
    def validate_effective_date(cls, v: date) -> date:
        """Valide que la date d'effet n'est pas dans le passé."""
        if v < date.today():
            raise ValueError("La date d'effet ne peut pas être dans le passé")
        return v


class PromotionUpdate(BaseModel):
    """
    Schéma pour la mise à jour partielle d'une promotion.
    Permet de modifier une promotion en statut draft ou pending_approval uniquement.
    """

    promotion_type: Optional[PromotionType] = None
    new_job_title: Optional[str] = None
    new_salary: Optional[Dict[str, Any]] = None
    new_statut: Optional[str] = None
    new_classification: Optional[Dict[str, Any]] = None
    effective_date: Optional[date] = None
    reason: Optional[str] = None
    justification: Optional[str] = None
    performance_review_id: Optional[str] = None
    grant_rh_access: Optional[bool] = None
    new_rh_access: Optional[RhAccessRole] = None

    @model_validator(mode="after")
    def validate_rh_access(self):
        """Valide que si grant_rh_access = True, alors new_rh_access doit être renseigné."""
        if self.grant_rh_access is True and self.new_rh_access is None:
            raise ValueError(
                "Si grant_rh_access est True, new_rh_access doit être renseigné"
            )
        return self

    @field_validator("effective_date")
    @classmethod
    def validate_effective_date(cls, v: Optional[date]) -> Optional[date]:
        """Valide que la date d'effet n'est pas dans le passé."""
        if v is not None and v < date.today():
            raise ValueError("La date d'effet ne peut pas être dans le passé")
        return v


class PromotionApprove(BaseModel):
    """
    Schéma pour l'approbation d'une promotion.

    Exemple:
    ```python
    {
        "notes": "Promotion approuvée suite à l'entretien annuel"
    }
    ```
    """

    notes: Optional[str] = Field(
        None,
        description="Notes optionnelles lors de l'approbation",
    )


class PromotionReject(BaseModel):
    """
    Schéma pour le rejet d'une promotion.

    Exemple:
    ```python
    {
        "rejection_reason": "Budget insuffisant pour cette période"
    }
    ```
    """

    rejection_reason: str = Field(
        ...,
        min_length=10,
        description="Raison du rejet (requis, minimum 10 caractères)",
    )


__all__ = [
    "PromotionCreate",
    "PromotionUpdate",
    "PromotionApprove",
    "PromotionReject",
]
