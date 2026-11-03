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

import re
from typing import Optional


def parse_email_allowlist(raw: Optional[str]) -> frozenset[str]:
    """Adresses exactes, comparaison casse-insensible.

    Séparateurs acceptés : virgule, point-virgule, espace — l'action
    deploy-cloudrun coupe les env_vars sur les virgules, donc la valeur
    déployée utilise des points-virgules.
    """
    if not raw:
        return frozenset()
    return frozenset(
        part.strip().lower()
        for part in re.split(r"[,;\s]+", raw)
        if part.strip()
    )


def is_direct_delivery_allowed(email: str, allowlist: frozenset[str]) -> bool:
    """True si l'adresse figure exactement dans l'allowlist (levée ciblée du redirect)."""
    return (email or "").strip().lower() in allowlist


#: Rôles d'un accès qui font d'un compte un compte « côté RH » (décision du 03/11/2026 :
#: les e-mails côté RH partent en direct, ceux des collaborateurs restent redirigés).
ROLES_COTE_RH = frozenset({"admin", "rh", "collaborateur_rh"})


def est_compte_rh(acces: list[dict], societes_custom_avec_droits_rh: set[str]) -> bool:
    """True si un accès actif est admin, rh ou collaborateur_rh, ou custom avec une permission RH
    dans sa société (même lecture que `core.security._resoudre_acces_rh_custom`)."""
    for a in acces or []:
        if not a.get("is_active", True):
            continue
        role = a.get("role")
        if role in ROLES_COTE_RH:
            return True
        if role == "custom" and str(a.get("company_id")) in societes_custom_avec_droits_rh:
            return True
    return False
