"""L'historique des versions d'un bulletin : numéros stables, plafond, recherche.

Les numéros valaient la longueur de la liste ; avec le plafond de dix versions,
ils se répétaient, et la restauration visait une position, pas un numéro : elle
rendait une autre version que celle choisie (audit du 28/09).
"""

from __future__ import annotations

from typing import Any

#: Versions antérieures gardées dans `edit_history`.
VERSIONS_CONSERVEES = 10

#: Auteur affiché quand une version a été archivée sans utilisateur connu
#: (régénération lancée par un script, un backtest).
AUTEUR_SYSTEME = "Système"


def _numero(entree: Any) -> int:
    if not isinstance(entree, dict):
        return 0
    try:
        return int(entree.get("version") or 0)
    except (TypeError, ValueError):
        return 0


def prochaine_version(historique: list[Any]) -> int:
    return max((_numero(e) for e in historique), default=0) + 1


def plafonner(historique: list[Any]) -> list[Any]:
    return list(historique)[-VERSIONS_CONSERVEES:]


def entree_de_version(historique: list[Any], version: int) -> dict[str, Any] | None:
    """La dernière entrée qui porte ce numéro (les anciens doublons comptent peu)."""
    trouvees = [e for e in historique if _numero(e) == int(version)]
    return trouvees[-1] if trouvees else None
