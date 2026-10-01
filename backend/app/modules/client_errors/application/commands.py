"""Enregistre une erreur d'écran : journal serveur, débit limité, pas de table."""

from __future__ import annotations

import time
from collections import defaultdict, deque
from typing import Any, Deque, Dict, Mapping

from app.core.logging import get_logger
from app.modules.client_errors.domain.rules import assainir_journal

logger = get_logger("modules.client_errors")

DEBIT_MAX = 20
FENETRE_S = 60

_attempts: Dict[str, Deque[float]] = defaultdict(deque)


class DebitClientErrorsDepasse(Exception):
    """Trop de signalements pour cet utilisateur dans la minute."""


def _autorise(cle: str, maintenant: float) -> bool:
    bucket = _attempts[cle]
    while bucket and maintenant - bucket[0] > FENETRE_S:
        bucket.popleft()
    if len(bucket) >= DEBIT_MAX:
        return False
    bucket.append(maintenant)
    return True


def enregistrer_erreur_ecran(
    user_id: str,
    brut: Mapping[str, Any] | None,
    *,
    maintenant: float | None = None,
) -> dict[str, str]:
    instant = maintenant if maintenant is not None else time.monotonic()
    if not _autorise(str(user_id or "inconnu"), instant):
        raise DebitClientErrorsDepasse()
    propre = assainir_journal(brut)
    logger.warning(
        "erreur-ecran user=%s ecran=%s action=%s message=%s pile=%s",
        user_id,
        propre["ecran"],
        propre["action"],
        propre["message"],
        propre["pile"],
    )
    return propre
