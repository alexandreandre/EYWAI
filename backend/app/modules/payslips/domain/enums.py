"""
Enums du domaine payslips.

Placeholder. Lors de la migration on pourra introduire des énumérations
(ex. type de bulletin, statut d'édition) si besoin.
"""

from __future__ import annotations

from enum import Enum


class PayslipGenerationMode(str, Enum):
    """Mode de génération (heures vs forfait jour)."""

    HEURES = "heures"
    FORFAIT_JOUR = "forfait_jour"
