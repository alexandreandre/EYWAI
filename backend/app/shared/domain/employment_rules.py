"""
Règles métier transverses liées au statut d'emploi (sans I/O).
"""

from __future__ import annotations


def is_forfait_jour(statut: str | None) -> bool:
    """True si le statut indique un forfait jour."""
    if not statut:
        return False
    return "forfait jour" in statut.lower()


def is_cadre(statut: str | None) -> bool:
    """Cadre / assimilé cadre (ex. « Cadre au forfait jour »), hors non-cadre."""
    compact = (statut or "").strip().lower().replace(" ", "").replace("-", "")
    return "cadre" in compact and "noncadre" not in compact


__all__ = ["is_forfait_jour", "is_cadre"]
