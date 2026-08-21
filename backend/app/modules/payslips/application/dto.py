"""
DTOs du module payslips.

Structures d'entrée/sortie des use cases et contexte utilisateur pour l'autorisation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


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
    """Génération refusée : calendrier du mois manquant ou incomplet (→ 422)."""

    code = "calendrier_incomplet"


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
class EditPayslipInput:
    """Entrée pour l'édition d'un bulletin."""

    payslip_id: str
    payslip_data: dict[str, Any]
    changes_summary: str
    current_user_id: str
    current_user_name: str
    pdf_notes: str | None = None
    internal_note: str | None = None


@dataclass
class RestorePayslipInput:
    """Entrée pour la restauration d'une version."""

    payslip_id: str
    version: int
    current_user_id: str
    current_user_name: str
