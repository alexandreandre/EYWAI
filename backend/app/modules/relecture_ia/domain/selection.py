"""Quels bulletins relire : seulement ceux modifiés depuis leur dernière relecture."""

from __future__ import annotations

from datetime import datetime
from typing import Any


def _instant(valeur: Any) -> datetime | None:
    try:
        return datetime.fromisoformat(str(valeur).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def meme_version(modifie_le: Any, relu_a_la_version: Any) -> bool:
    """Vrai si le bulletin n'a pas bougé depuis la version relue. Dans le doute, faux."""
    a, b = _instant(modifie_le), _instant(relu_a_la_version)
    return a is not None and a == b


def bulletins_a_relire(
    bulletins: list[dict[str, Any]], deja_relus: dict[str, Any]
) -> list[dict[str, Any]]:
    """`deja_relus` : pour chaque bulletin, le repère de modification de sa dernière relecture."""
    return [
        b
        for b in bulletins
        # Une régularisation n'est pas la paie d'un mois : pas de mois précédent à comparer.
        if not b.get("bulletin_kind") and not meme_version(b.get("updated_at"), deja_relus.get(str(b["id"])))
    ]
