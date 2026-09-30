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


class PayslipRefusStructure(Exception):
    """Refus de génération que l'écran sait lire.

    Le `detail` HTTP est `{code, message, **details}` (`detail_http()`), avec
    le statut `http_status`. Le recalcul après une correction rend le même objet.
    (Pas d'attribut `detail` : `corrections._message_d_erreur` lit celui des
    HTTPException.)
    """

    code: str = ""
    http_status: int = 422

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.details: dict[str, Any] = dict(details or {})

    def detail_http(self) -> dict[str, Any]:
        return {"code": self.code, "message": str(self), **self.details}


class PayslipCalendarIncompleteError(PayslipRefusStructure):
    """Des jours de la période à saisir manquent (422).

    `details` : `fenetre`, `jours_manquants`, `jours_informatifs`.
    """

    code = "calendrier_incomplet"


class PayslipHeuresSurArretError(PayslipRefusStructure):
    """Des heures sont saisies un jour d'arrêt ou d'absence non travaillée (422).
    Aucun forçage : la seule sortie est une correction (effacer les heures, ou
    modifier l'absence).

    `details` : `jours` (`[{annee, mois, jour, heures}]`).
    """

    code = "heures_sur_jour_d_arret"


class PayslipArretsIllisiblesError(PayslipRefusStructure):
    """Les arrêts validés n'ont pas pu être lus (503) : sans eux, la garde
    laisserait passer des heures un week-end d'arrêt. Rien n'est calculé ; il
    suffit de réessayer."""

    code = "arrets_illisibles"
    http_status = 503


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
