"""
Règles métier transverses liées au statut d'emploi (sans I/O).
"""

from __future__ import annotations


def is_forfait_jour(statut: str | None) -> bool:
    """True si le statut indique un forfait jour."""
    if not statut:
        return False
    return "forfait jour" in statut.lower()


__all__ = ["is_forfait_jour"]
