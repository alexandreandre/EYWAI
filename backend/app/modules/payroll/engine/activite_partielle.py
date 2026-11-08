"""Activité partielle : les heures et le taux imprimés sur le bulletin."""

from __future__ import annotations

from typing import Dict


def heures_et_taux(montant: float, heures: float) -> Dict[str, float]:
    """Colonnes « base » et « taux » d'une ligne d'activité partielle.

    Rien sans heures saisies : le taux ne s'invente pas.
    """
    if heures <= 0:
        return {}
    return {"quantite": round(heures, 2), "taux": round(abs(montant) / heures, 4)}
