"""Value objects du domaine net_entreprises (sans dépendance FastAPI ni DB)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional


class TransmissionMode(str, Enum):
    """Mode de dépôt de la DSN."""

    MANUAL = "manual"  # Dépôt manuel sur net-entreprises.fr (défaut)
    API_CERTIFICAT = "api_certificat"  # API machine-to-machine via certificat
    API_DECLARANT = "api_declarant"  # API via identifiant déclarant


class TransmissionStatus(str, Enum):
    """Cycle de vie d'une transmission DSN."""

    GENERATED = "generated"  # Fichier généré, pas encore déposé
    MANUAL = "manual"  # À déposer / déposé manuellement
    QUEUED = "queued"  # En file d'envoi (API)
    SENT = "sent"  # Envoyé à Net-entreprises
    ACKNOWLEDGED = "acknowledged"  # Accusé de réception reçu
    REJECTED = "rejected"  # Rejeté (anomalies CRM)


# Statuts considérés comme « terminaux positifs » pour le suivi.
SUCCESS_STATUSES = frozenset({TransmissionStatus.ACKNOWLEDGED.value})
# Statuts nécessitant une action.
PENDING_STATUSES = frozenset(
    {
        TransmissionStatus.GENERATED.value,
        TransmissionStatus.MANUAL.value,
        TransmissionStatus.QUEUED.value,
        TransmissionStatus.SENT.value,
    }
)


def is_api_mode(mode: str) -> bool:
    """Vrai si le mode implique un envoi via l'API Net-entreprises."""
    return mode in (TransmissionMode.API_CERTIFICAT.value, TransmissionMode.API_DECLARANT.value)


@dataclass(frozen=True)
class ConnectionTestResult:
    """Résultat d'un test de connexion (sans secret)."""

    success: bool
    status: str  # 'success' | 'failure' | 'manual' | 'not_configured'
    message: str


@dataclass(frozen=True)
class TransmissionResult:
    """Résultat d'une tentative de dépôt DSN par un connecteur."""

    status: str  # valeur de TransmissionStatus
    mode: str  # valeur de TransmissionMode
    message: str
    net_entreprises_ref: Optional[str] = None
    error_message: Optional[str] = None
    crm_retour: Optional[Dict[str, Any]] = field(default=None)


@dataclass(frozen=True)
class IjDecompteLine:
    """Ligne de décompte IJSS CPAM."""

    amount: float
    payment_date: Optional[str] = None
    employee_nir: Optional[str] = None
    employee_name: Optional[str] = None
    period_start: Optional[str] = None
    period_end: Optional[str] = None
    net_entreprises_ref: Optional[str] = None


@dataclass(frozen=True)
class IjDecomptesFetchResult:
    """Résultat récupération décomptes IJ via Net-Entreprises."""

    success: bool
    status: str  # success | not_available | not_configured | error
    message: str
    lines: tuple[IjDecompteLine, ...] = field(default_factory=tuple)
