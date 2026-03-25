"""
Schémas réponses du module monthly_inputs.

Formes de réponse identiques à l'existant (api/routers/monthly_inputs.py).
"""

from __future__ import annotations

from typing import Any

# Réponses actuelles : listes de dict bruts ou {"status": "success", ...}
# Pas de modèle strict côté API pour garder la compatibilité exacte.
# Typage optionnel pour usage interne / doc.


def create_batch_response(inserted_count: int) -> dict[str, Any]:
    """Réponse POST /api/monthly-inputs (batch)."""
    return {"status": "success", "inserted": inserted_count}


def create_single_response(inserted_data: dict[str, Any]) -> dict[str, Any]:
    """Réponse POST /api/employees/{id}/monthly-inputs."""
    return {"status": "success", "inserted_data": inserted_data}


def delete_response() -> dict[str, str]:
    """Réponse DELETE monthly-inputs."""
    return {"status": "success"}
