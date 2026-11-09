"""Limite de débit des surfaces publiques (R-668, 09/11/2026).

Fenêtre glissante d'une minute, par surface et par adresse IP, en mémoire : le
compte est propre à chaque instance du serveur. Elle freine un essai en masse
(mots de passe, jetons d'activation) ; elle ne remplace pas le plafond que
Supabase Auth applique de son côté, et ne prétend pas compter au global.
"""

from __future__ import annotations

import time
from collections import deque
from typing import Callable, Deque, Dict, Tuple

from fastapi import HTTPException, Request, status

FENETRE_SECONDES = 60
MAX_CLES_SUIVIES = 10_000

_essais: Dict[Tuple[str, str], Deque[float]] = {}


def _adresse(request: Request) -> str:
    return request.client.host if request.client else "inconnue"


def _purger(maintenant: float) -> None:
    """Oublie les clés expirées quand la table grossit : la mémoire reste bornée."""
    if len(_essais) < MAX_CLES_SUIVIES:
        return
    for cle in [c for c, f in _essais.items() if not f or maintenant - f[-1] > FENETRE_SECONDES]:
        del _essais[cle]
    if len(_essais) >= MAX_CLES_SUIVIES:
        _essais.clear()


def limite_de_debit(surface: str, par_minute: int) -> Callable[[Request], None]:
    """Dépendance FastAPI : au-delà de `par_minute` appels, répond 429."""

    def garde_de_debit(request: Request) -> None:
        maintenant = time.monotonic()
        _purger(maintenant)
        file = _essais.setdefault((surface, _adresse(request)), deque())
        while file and maintenant - file[0] > FENETRE_SECONDES:
            file.popleft()
        if len(file) >= par_minute:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Trop de tentatives. Réessayez dans une minute.",
            )
        file.append(maintenant)

    return garde_de_debit
