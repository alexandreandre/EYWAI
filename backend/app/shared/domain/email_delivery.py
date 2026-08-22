"""
Règles pures de délivrance directe des e-mails sous redirect global.

EMAIL_FORCE_REDIRECT_TO (posé en prod depuis le 07/08) détourne TOUT le
trafic sortant vers une boîte interne. La levée est CIBLÉE : seules les
adresses listées, à l'exactitude près, dans ACTIVATION_EMAIL_ALLOWLIST
reçoivent leurs e-mails en direct — et ce sur TOUS les flux (activation,
réinitialisation de mot de passe, notifications), sinon un utilisateur de
la vague 0 resterait joignable à l'invitation mais sourd au reset.

Aucune dépendance : consommé par le smtp_sender (application du redirect)
et par le module activation (refus d'inviter un destinataire non levé).
"""

from __future__ import annotations

from typing import Optional


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
