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


def chemin_pdf_de_version(pdf_storage_path: str, version: int) -> str:
    """`…/Bulletin_X_08-2026.pdf` → `…/Bulletin_X_08-2026_v4.pdf`."""
    base = pdf_storage_path[:-4] if pdf_storage_path.lower().endswith(".pdf") else pdf_storage_path
    return f"{base}_v{int(version)}.pdf"


def pdfs_sortis(avant: list[Any], apres: list[Any]) -> list[str]:
    """Les PDF des versions que le plafond vient de retirer de l'historique."""
    gardes = {id(e) for e in apres}
    return [
        str(e["pdf_storage_path"])
        for e in avant
        if id(e) not in gardes and isinstance(e, dict) and e.get("pdf_storage_path")
    ]
