"""
Schémas de réponse API pour le module promotions.

Définitions canoniques (migrées depuis schemas.promotion). Comportement identique.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


# Types littéraux pour les statuts et types de promotion
PromotionStatus = Literal[
    "draft",
    "pending_approval",
    "approved",
    "rejected",
    "effective",
    "cancelled",
]

PromotionType = Literal[
    "poste",
    "salaire",
    "statut",
    "classification",
    "mixte",
]

RhAccessRole = Literal[
    "collaborateur_rh",
    "rh",
    "admin",
]


class PromotionBase(BaseModel):
    """Schéma de base pour une promotion."""

    promotion_type: PromotionType
    previous_job_title: Optional[str] = None
    previous_salary: Optional[Dict[str, Any]] = None
    previous_statut: Optional[str] = None
    previous_classification: Optional[Dict[str, Any]] = None
    new_job_title: Optional[str] = None
    new_salary: Optional[Dict[str, Any]] = None
    new_statut: Optional[str] = None
    new_classification: Optional[Dict[str, Any]] = None
    previous_rh_access: Optional[str] = None
    new_rh_access: Optional[RhAccessRole] = None
    grant_rh_access: bool = False
    effective_date: date
    request_date: date = Field(default_factory=date.today)
    status: PromotionStatus = "draft"
    reason: Optional[str] = None
    justification: Optional[str] = None
    performance_review_id: Optional[str] = None
    requested_by: Optional[str] = None
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    notes: Optional[List[Dict[str, Any]]] = None
    promotion_letter_url: Optional[str] = None


class PromotionRead(BaseModel):
    """
    Schéma pour la lecture complète d'une promotion.
    Inclut tous les champs de la table, y compris les métadonnées.
    """

    id: str
    company_id: str
    employee_id: str
    promotion_type: PromotionType
    previous_job_title: Optional[str] = None
    previous_salary: Optional[Dict[str, Any]] = None
    previous_statut: Optional[str] = None
    previous_classification: Optional[Dict[str, Any]] = None
    new_job_title: Optional[str] = None
    new_salary: Optional[Dict[str, Any]] = None
    new_statut: Optional[str] = None
    new_classification: Optional[Dict[str, Any]] = None
    previous_rh_access: Optional[str] = None
    new_rh_access: Optional[RhAccessRole] = None
    grant_rh_access: bool = False
    effective_date: date
    request_date: date
    status: PromotionStatus
    reason: Optional[str] = None
    justification: Optional[str] = None
    performance_review_id: Optional[str] = None
    requested_by: Optional[str] = None
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    notes: Optional[List[Dict[str, Any]]] = None
    promotion_letter_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PromotionListItem(BaseModel):
    """
    Schéma pour un item de la liste des promotions.
    Version allégée pour l'affichage dans un tableau.
    """

    id: str
    employee_id: str
    first_name: str = Field(..., description="Prénom de l'employé")
    last_name: str = Field(..., description="Nom de l'employé")
    promotion_type: PromotionType
    new_job_title: Optional[str] = None
    new_salary: Optional[Dict[str, Any]] = None
    new_statut: Optional[str] = None
    effective_date: date
    status: PromotionStatus
    request_date: date
    requested_by_name: Optional[str] = Field(None, description="Nom du demandeur")
    approved_by_name: Optional[str] = Field(None, description="Nom de l'approbateur")
    grant_rh_access: bool = False
    new_rh_access: Optional[RhAccessRole] = None
    performance_review_id: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class EmployeeRhAccess(BaseModel):
    """
    Schéma pour l'accès RH actuel d'un employé.
    Utilisé par l'endpoint GET /api/employees/{employee_id}/rh-access
    """

    has_access: bool = Field(
        ...,
        description="Indique si l'employé a actuellement des accès RH",
    )
    current_role: Optional[str] = Field(
        None,
        description="Rôle RH actuel (collaborateur_rh, rh, admin) ou null si aucun accès",
    )
    can_grant_access: bool = Field(
        ...,
        description="Indique si l'utilisateur connecté peut donner des accès RH à cet employé",
    )
    available_roles: List[RhAccessRole] = Field(
        ...,
        description="Liste des rôles RH disponibles selon le rôle actuel de l'employé",
    )


class PromotionStats(BaseModel):
    """
    Schéma pour les statistiques des promotions.
    Utilisé par l'endpoint GET /api/promotions/stats
    """

    total_promotions: int = Field(..., description="Nombre total de promotions")
    promotions_by_month: Dict[str, int] = Field(
        ...,
        description='Nombre de promotions par mois (clé: "YYYY-MM", valeur: count)',
    )
    approval_rate: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Taux d'approbation en pourcentage",
    )
    promotions_by_type: Dict[str, int] = Field(
        ...,
        description="Nombre de promotions par type",
    )
    average_salary_increase: Optional[float] = Field(
        None,
        description="Augmentation moyenne de salaire en pourcentage (si applicable)",
    )
    promotions_with_rh_access: int = Field(
        ...,
        description="Nombre de promotions incluant un changement d'accès RH",
    )


__all__ = [
    "PromotionStatus",
    "PromotionType",
    "RhAccessRole",
    "PromotionBase",
    "PromotionRead",
    "PromotionListItem",
    "EmployeeRhAccess",
    "PromotionStats",
]
