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

TOKEN_BYTE_LENGTH = 32
TOKEN_VALIDITY_DAYS = 7
# Alignée sur la règle existante du reset (frontend ResetPassword + schémas users).
PASSWORD_MIN_LENGTH = 8

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


def validate_activation_password(password: str) -> Optional[str]:
    """Retourne un message d'erreur, ou None si le mot de passe est acceptable."""
    if len(password or "") < PASSWORD_MIN_LENGTH:
        return (
            "Le mot de passe doit contenir au moins "
            f"{PASSWORD_MIN_LENGTH} caractères."
        )
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


def parse_email_allowlist(raw: Optional[str]) -> frozenset[str]:
    """Adresses exactes séparées par des virgules, comparaison casse-insensible."""
    if not raw:
        return frozenset()
    return frozenset(
        part.strip().lower() for part in raw.split(",") if part.strip()
    )


def is_direct_delivery_allowed(email: str, allowlist: frozenset[str]) -> bool:
    """True si l'adresse figure exactement dans l'allowlist (levée ciblée du redirect)."""
    return (email or "").strip().lower() in allowlist
