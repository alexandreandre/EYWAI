"""
Value objects pour le module bonus_types.

Résultat pur du calcul de montant (sans dépendance HTTP/API).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BonusAmountComputation:
    """
    Résultat du calcul de montant d'une prime (règle métier pure).

    - amount: montant calculé
    - total_hours: présent uniquement pour type selon_heures
    - seuil: présent uniquement pour type selon_heures
    - condition_met: présent uniquement pour type selon_heures (heures >= seuil)
    """

    amount: float
    total_hours: float | None = None
    seuil: float | None = None
    condition_met: bool | None = None
