"""
Règles métier pures du lien d'activation (aucune dépendance FastAPI/DB/HTTP).

Le jeton est MAISON : usage unique, expiration 7 jours, jamais stocké en
clair (empreinte sha256 hex uniquement). Aucun mécanisme externe ne
transparaît nulle part.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.modules.employees.domain.rules import is_dsn_import_placeholder_email
from app.shared.domain.email_delivery import (  # noqa: F401 — ré-export historique
    is_direct_delivery_allowed,
    parse_email_allowlist,
)

TOKEN_BYTE_LENGTH = 32
TOKEN_VALIDITY_DAYS = 7
# Alignée sur les règles du front (Activation.tsx) : mêmes 4 exigences.
PASSWORD_MIN_LENGTH = 8

# Statuts d'emploi considérés actifs pour l'invitation. La base porte les
# trois graphies ; « en_onboarding » est précisément la cible de la vague 0.
ACTIVE_EMPLOYMENT_STATUSES = frozenset({"actif", "active", "en_onboarding"})

# Le MÊME message pour tous les échecs de jeton : pas d'énumération possible.
GENERIC_TOKEN_ERROR_MESSAGE = "Lien invalide ou expiré"


@dataclass(frozen=True)
class GeneratedActivationToken:
    raw_token: str
    token_hash: str


def generate_activation_token() -> GeneratedActivationToken:
    raw = secrets.token_urlsafe(TOKEN_BYTE_LENGTH)
    return GeneratedActivationToken(
        raw_token=raw,
        token_hash=hash_activation_token(raw),
    )


def hash_activation_token(raw_token: str) -> str:
    normalized = (raw_token or "").strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def token_matches(stored_hash: str, raw_token: str) -> bool:
    """Comparaison en temps constant entre l'empreinte stockée et le jeton reçu."""
    computed = hash_activation_token(raw_token)
    return hmac.compare_digest(str(stored_hash or ""), computed)


def is_invitable_email(email: Optional[str]) -> bool:
    """Adresse réelle uniquement : non vide et jamais fabriquée par la plateforme."""
    value = (email or "").strip()
    if not value or "@" not in value:
        return False
    return not is_dsn_import_placeholder_email(value)


def mask_email(email: str) -> str:
    """j***@exemple.fr — jamais l'adresse complète dans les réponses RH."""
    value = (email or "").strip()
    local, sep, domain = value.partition("@")
    if not sep or not local:
        return "***"
    return f"{local[0]}***@{domain}"


def is_activable_employment_status(status: Optional[str]) -> bool:
    """Statut vide = actif (fiches historiques sans statut renseigné)."""
    value = (status or "").strip().lower()
    return not value or value in ACTIVE_EMPLOYMENT_STATUSES


def validate_activation_password(password: str) -> Optional[str]:
    """Retourne un message d'erreur, ou None si le mot de passe est acceptable.

    Mêmes 4 règles que le front : le serveur est la barrière, pas l'écran.
    """
    value = password or ""
    if len(value) < PASSWORD_MIN_LENGTH:
        return (
            "Le mot de passe doit contenir au moins "
            f"{PASSWORD_MIN_LENGTH} caractères."
        )
    if not any(c.isupper() for c in value):
        return "Le mot de passe doit contenir au moins une majuscule."
    if not any(c.islower() for c in value):
        return "Le mot de passe doit contenir au moins une minuscule."
    if not any(c.isdigit() for c in value):
        return "Le mot de passe doit contenir au moins un chiffre."
    return None


def _parse_timestamp(value: Any) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def is_token_expired(row: Dict[str, Any], now: Optional[datetime] = None) -> bool:
    expires_at = _parse_timestamp(row.get("expires_at"))
    if expires_at is None:
        return True
    return (now or datetime.now(timezone.utc)) > expires_at


def is_token_alive(row: Optional[Dict[str, Any]], now: Optional[datetime] = None) -> bool:
    """Vivant = jamais utilisé, jamais invalidé, pas expiré."""
    if not row:
        return False
    if row.get("used_at") or row.get("invalidated_at"):
        return False
    return not is_token_expired(row, now)


