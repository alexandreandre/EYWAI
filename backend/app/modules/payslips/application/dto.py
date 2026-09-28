"""
DTOs du module payslips.

Structures d'entrée/sortie des use cases et contexte utilisateur pour l'autorisation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from app.modules.payslips.domain.corrections import CorrectionsBulletin


# --- Exceptions applicatives (le router mappe vers 403/404) ---
class PayslipNotFoundError(Exception):
    """Bulletin non trouvé."""

    pass


class PayslipForbiddenError(Exception):
    """Accès refusé au bulletin (permissions insuffisantes)."""

    pass


class PayslipBadRequestError(Exception):
    """Requête invalide (ex. bulletin sans entreprise associée)."""

    pass


class PayslipCriticalActiveError(Exception):
    """Validation impossible : alertes critiques encore actives."""

    def __init__(self, critical_alerts: list[dict[str, Any]]):
        self.critical_alerts = critical_alerts
        super().__init__("Alertes critiques actives")


class PayslipCalendarIncompleteError(Exception):
    """Génération refusée : des jours de la période à saisir manquent (→ 422).

    `details` : `fenetre`, `jours_manquants`, `jours_informatifs` — repris tels
    quels dans le `detail` HTTP, en plus de `code` et `message`.
    """

    code = "calendrier_incomplet"

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.details: dict[str, Any] = dict(details or {})


class PayslipConflictError(Exception):
    """Le bulletin a changé depuis que l'écran l'a lu (→ 409)."""


class PayslipValidatedError(Exception):
    """Génération refusée : un bulletin validé existe déjà pour la période (→ 409)."""

    code = "bulletin_valide"


@dataclass
class UserContext:
    """
    Contexte utilisateur pour les contrôles d'accès dans l'application.
    Permet de ne pas dépendre du modèle User du module users.
    """

    user_id: str
    is_platform_admin: bool
    has_rh_access_in_company: Callable[[str], bool]
    active_company_id: str | None
    resolved_employee_id: str | None = None
    first_name: str | None = None
    last_name: str | None = None

    def display_name(self) -> str:
        """Nom affiché pour l'historique (édition, restauration)."""
        parts = [self.first_name or "", self.last_name or ""]
        name = " ".join(parts).strip()
        return name or "Utilisateur"


@dataclass
class GeneratePayslipInput:
    """Entrée pour la génération d'un bulletin.

    Les overrides (`force_calendrier_incomplet`, `regenerer_bulletin_valide`)
    sont explicites et tracés ; le défaut est toujours le refus.
    """

    employee_id: str
    year: int
    month: int
    force_calendrier_incomplet: bool = False
    regenerer_bulletin_valide: bool = False
    requested_by: str | None = None
    requested_by_name: str | None = None
    #: Ce qui a été changé avant cette régénération (correction au bulletin,
    #: restauration) : écrit dans l'historique à la place du motif générique.
    motif: str | None = None


@dataclass
class GeneratePayslipResult:
    """Résultat de la génération (status, message, download_url, alertes RH).

    `warnings` mêle chaînes (alertes RH du moteur) et dicts `{code, message}`
    (avertissements de garde, ex. `calendrier_incomplet_force`).
    """

    status: str
    message: str
    download_url: str
    payslip_id: str | None = None
    warnings: list[Any] | None = None


@dataclass
class CorrigerBulletinInput:
    """Entrée pour la correction d'un bulletin par ses variables du mois.

    `pdf_notes` à None laisse la note du bulletin telle quelle ; une chaîne vide
    l'efface. `base_updated_at` est la date de mise à jour du bulletin lu par
    l'écran : s'il a changé depuis, la correction est refusée.
    """

    payslip_id: str
    corrections: CorrectionsBulletin
    current_user_id: str
    current_user_name: str
    changes_summary: str | None = None
    pdf_notes: str | None = None
    internal_note: str | None = None
    base_updated_at: str | None = None


@dataclass
class RestorePayslipInput:
    """Entrée pour la restauration d'une version."""

    payslip_id: str
    version: int
    current_user_id: str
    current_user_name: str
