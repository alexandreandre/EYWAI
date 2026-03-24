"""
Schémas Pydantic sortie API du module employees.

Définitions canoniques : employé complet, réponse création, URL contrat/credentials.
ContractResponse depuis app.shared ; PromotionListItem et EmployeeRhAccess définis
localement pour les sous-routes employé (même structure que le module promotions).
"""
from datetime import date, datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.shared.schemas import ContractResponse

# Types littéraux pour les réponses promotion (alignés sur le module promotions)
PromotionStatus = Literal[
    "draft", "pending_approval", "approved", "rejected", "effective", "cancelled",
]
PromotionType = Literal[
    "poste", "salaire", "statut", "classification", "mixte",
]
RhAccessRole = Literal["collaborateur_rh", "rh", "admin"]


class PromotionListItem(BaseModel):
    """Item de liste des promotions (sous-route GET .../promotions)."""
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
    """Accès RH actuel d'un employé (sous-route GET .../rh-access)."""
    has_access: bool = Field(..., description="Indique si l'employé a des accès RH")
    current_role: Optional[str] = Field(None, description="Rôle RH actuel ou null")
    can_grant_access: bool = Field(..., description="L'utilisateur peut donner des accès RH")
    available_roles: List[RhAccessRole] = Field(..., description="Rôles RH disponibles")


class FullEmployee(BaseModel):
    """Employé complet (lecture, détail, liste)."""

    id: str
    employee_folder_name: str
    username: str  # Nom d'utilisateur pour la connexion
    # Section Salarié
    first_name: str
    last_name: str
    email: EmailStr | None = None
    nir: str | None = None
    date_naissance: date | None = None
    lieu_naissance: str | None = None
    nationalite: str | None = None
    adresse: Dict[str, Any] | None = None
    coordonnees_bancaires: Dict[str, Any] | None = None
    # Section Contrat
    hire_date: date | None = None
    contract_type: str | None = None
    statut: str | None = None
    job_title: str | None = None
    periode_essai: Dict[str, Any] | None = None
    is_temps_partiel: bool | None = None
    duree_hebdomadaire: float | None = None
    # Section Rémunération
    salaire_de_base: Dict[str, Any] | None = None
    classification_conventionnelle: Dict[str, Any] | None = None
    elements_variables: Dict[str, Any] | None = None
    avantages_en_nature: Dict[str, Any] | None = None
    # Section Spécificités
    specificites_paie: Dict[str, Any] | None = None
    # Section Titre de séjour (champs bruts de la DB)
    is_subject_to_residence_permit: bool | None = None
    residence_permit_expiry_date: date | None = None
    residence_permit_type: str | None = None
    residence_permit_number: str | None = None
    employment_status: str | None = None
    # Section Titre de séjour (données calculées par le backend)
    residence_permit_status: str | None = None  # "valid", "to_renew", "expired", "to_complete"
    residence_permit_days_remaining: int | None = None
    residence_permit_data_complete: bool | None = None
    # Section Entretien annuel (données calculées pour l'année courante)
    annual_review_current_status: str | None = None
    annual_review_current_year: int | None = None
    annual_review_current_planned_date: date | None = None
    annual_review_current_completed_date: date | None = None
    # Convention collective (optionnel: si null, utilise celle de l'entreprise)
    collective_agreement_id: str | None = None

    @field_validator("email", mode="before")
    @classmethod
    def empty_email_to_none(cls, v: object) -> object:
        """La DB peut renvoyer '' ; EmailStr rejette la chaîne vide, pas None."""
        if v is None:
            return None
        if isinstance(v, str) and not v.strip():
            return None
        return v


class NewEmployeeResponse(FullEmployee):
    """Modèle de réponse pour la création d'un employé, incluant le mot de passe généré."""

    generated_password: str
    username: str  # Renvoyer aussi le username pour l'afficher à l'utilisateur
    warnings: List[str] | None = None  # Ex: "RIB en doublon avec ..."


__all__ = [
    "FullEmployee",
    "NewEmployeeResponse",
    "ContractResponse",
    "EmployeeRhAccess",
    "PromotionListItem",
]
