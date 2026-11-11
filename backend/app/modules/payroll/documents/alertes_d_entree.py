"""Ce que la fiche oublie et que le bulletin doit dire, sans arrêter le calcul.

La commande de génération (`payslips.application.commands._alertes_d_entree`)
les pose pour la durée d'une génération ; les deux générateurs (heures, forfait
jours) les ajoutent aux alertes du bulletin. Une variable de contexte plutôt qu'un
paramètre : les générateurs gardent leur signature, le bac à sable n'en voit
aucune.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any

_ALERTES: ContextVar[tuple[dict[str, Any], ...]] = ContextVar("alertes_d_entree", default=())


@contextmanager
def alertes_d_entree(alertes: list[dict[str, Any]] | None) -> Iterator[None]:
    jeton = _ALERTES.set(tuple(dict(a) for a in alertes or [] if isinstance(a, dict)))
    try:
        yield
    finally:
        _ALERTES.reset(jeton)


def alertes_d_entree_courantes() -> list[dict[str, Any]]:
    return [dict(a) for a in _ALERTES.get()]
