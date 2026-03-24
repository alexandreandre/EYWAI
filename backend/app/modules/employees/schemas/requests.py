"""
Schémas Pydantic entrée API du module employees.

Définitions canoniques : création et mise à jour d'un employé.
Comportement identique à l'ancien schemas.employee (NewFullEmployee, UpdateEmployee).
"""
from datetime import date
from typing import Any, Dict

from pydantic import BaseModel, EmailStr


class NewFullEmployee(BaseModel):
    """Données requises pour la création d'un employé."""

    # Salarié
    first_name: str
    last_name: str
    email: EmailStr
    nir: str
    date_naissance: date
    lieu_naissance: str
    nationalite: str
    adresse: Dict[str, Any]
    coordonnees_bancaires: Dict[str, Any]
    # Titre de séjour (optionnel)
    is_subject_to_residence_permit: bool | None = None
    residence_permit_expiry_date: date | None = None
    residence_permit_type: str | None = None
    residence_permit_number: str | None = None
    # Contrat
    hire_date: date
    contract_type: str
    statut: str
    job_title: str
    periode_essai: Dict[str, Any] | None = None
    is_temps_partiel: bool
    duree_hebdomadaire: float
    # Rémunération
    salaire_de_base: Dict[str, Any]
    classification_conventionnelle: Dict[str, Any]
    elements_variables: Dict[str, Any] | None = None
    avantages_en_nature: Dict[str, Any] | None = None
    # Spécificités
    specificites_paie: Dict[str, Any]
    # Convention collective (optionnel: si null, utilise celle de l'entreprise)
    collective_agreement_id: str | None = None


class UpdateEmployee(BaseModel):
    """
    Modèle pour la mise à jour des informations d'un salarié.
    Tous les champs sont optionnels (y compris coordonnées bancaires pour l'édition RH).
    """

    first_name: str | None = None
    last_name: str | None = None
    collective_agreement_id: str | None = None
    email: EmailStr | None = None
    phone_number: str | None = None
    adresse: Dict[str, Any] | None = None
    coordonnees_bancaires: Dict[str, Any] | None = None


__all__ = ["NewFullEmployee", "UpdateEmployee"]
