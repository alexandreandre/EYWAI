"""
Schémas Pydantic entrée API du module absences.

Migrés depuis schemas/absence.py — comportement identique.
"""

from datetime import date
from typing import List, Literal, Optional

from pydantic import BaseModel, model_validator

from app.modules.absences.domain.enums import IJSS_ELIGIBLE_TYPES
from app.shared.domain.absence_calendar import daterange_days

AbsenceType = Literal[
    "conge_paye",
    "rtt",
    "jtc",
    "sans_solde",
    "repos_compensateur",
    "recuperation_modulation",
    "evenement_familial",
    "arret_maladie",
    "arret_at",
    "arret_paternite",
    "arret_maternite",
    "arret_maladie_pro",
]
AbsenceStatus = Literal["pending", "validated", "rejected", "cancelled"]

ArretType = Literal[
    "maladie_simple",
    "accident_travail",
    "maladie_professionnelle",
    "accident_trajet",
    "mi_temps_therapeutique",
    "ald",
    "rechute_at",
    "arret_exceptionnel",
]

# Liste canonique du domaine (arrêts avec attestation / IJSS) : le front
# (ARRET_PRINCIPAL_TYPES) et le script de réparation gardent la même source.
_ARRETS_TYPES_PRINCIPAUX = IJSS_ELIGIBLE_TYPES

# Garde-fou de saisie : une période d'arrêt au-delà de ~3 ans est presque
# sûrement une faute de frappe sur l'année (l'expansion calendaire stockerait
# des milliers de jours et le calendrier serait réécrit sur autant de mois).
_PERIODE_ARRET_MAX_JOURS = 1096


class AbsenceRequestCreate(BaseModel):
    """Schéma pour la création d'une demande d'absence par un employé."""

    employee_id: str
    type: AbsenceType
    # Saisie jour par jour (congés, mi-temps thérapeutique, historique)…
    selected_days: List[date] = []
    # …ou saisie par période calendaire (arrêts) : le serveur étend en jours,
    # week-ends et fériés compris (spec 2026-09-01 arrêts jours calendaires).
    date_debut: Optional[date] = None
    date_fin: Optional[date] = None
    comment: str | None = None
    attachment_url: str | None = None
    filename: str | None = None
    event_subtype: str | None = (
        None  # Requis si type = evenement_familial (ex: mariage_salarie, deces_enfant)
    )
    arret_type: Optional[ArretType] = None

    @model_validator(mode="after")
    def arret_type_required_for_arrets(self) -> "AbsenceRequestCreate":
        if self.type in _ARRETS_TYPES_PRINCIPAUX and self.arret_type is None:
            raise ValueError(
                "Le type d'arrêt est obligatoire pour ce type d'absence (arrêt / congé pathologique)."
            )
        return self

    @model_validator(mode="after")
    def periode_ou_jours(self) -> "AbsenceRequestCreate":
        a_periode = self.date_debut is not None or self.date_fin is not None
        if a_periode:
            if self.date_debut is None or self.date_fin is None:
                raise ValueError(
                    "Une période d'arrêt doit porter une date de début ET une date de fin."
                )
            if self.date_fin < self.date_debut:
                raise ValueError(
                    "La date de fin de l'arrêt est antérieure à sa date de début."
                )
            if self.selected_days:
                raise ValueError(
                    "Fournissez soit des jours sélectionnés, soit une période, pas les deux."
                )
            if self.type not in _ARRETS_TYPES_PRINCIPAUX:
                raise ValueError(
                    "La saisie par période (du … au …) est réservée aux arrêts de travail."
                )
            if self.arret_type == "mi_temps_therapeutique":
                raise ValueError(
                    "Un mi-temps thérapeutique se saisit jour par jour "
                    "(le salarié travaille partiellement), pas par période."
                )
            if (self.date_fin - self.date_debut).days + 1 > _PERIODE_ARRET_MAX_JOURS:
                raise ValueError(
                    "Période d'arrêt de plus de 3 ans — vérifiez les dates saisies."
                )
            # L'expansion calendaire vit ICI, à la frontière d'entrée : la
            # commande ne consomme qu'un seul contrat, selected_days, comme
            # toutes les autres origines de saisie (import DSN compris).
            self.selected_days = daterange_days(self.date_debut, self.date_fin)
        # « ni jours ni période » n'est PAS refusé ici : la commande le rejette
        # en ValueError → 400 « validation métier », contrat d'API historique
        # (cf. test_create_absence_request_empty_selected_days_returns_400).
        return self


class AbsenceRequestStatusUpdate(BaseModel):
    """Schéma pour la mise à jour du statut d'une demande."""

    status: AbsenceStatus
    subrogation_active: Optional[bool] = None


class SalaryCertificateTransmissionUpdate(BaseModel):
    """Marquage transmission attestation vers CPAM / Net-Entreprises."""

    transmitted_to_cpam: bool = True


class ManagerApprovalRequest(BaseModel):
    """Validation ou refus par le manager (étape avant RH)."""

    approved: bool
    rejection_reason: str | None = None
