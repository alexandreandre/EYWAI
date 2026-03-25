"""
DTOs du module monthly_inputs.

Objets de transfert applicatifs (optionnel : l'API actuelle renvoie des dict).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass
class CreateBatchResultDto:
    """Résultat de la création en batch."""

    inserted_count: int


@dataclass
class CreateSingleResultDto:
    """Résultat de la création d'une saisie."""

    inserted_data: Dict[str, Any]


@dataclass
class ListMonthlyInputsResultDto:
    """Liste de saisies (dict bruts pour compatibilité)."""

    items: List[Dict[str, Any]]
