"""
DTOs et exceptions du module saisies_avances.

Exceptions levées par la couche application ; le router les convertit en HTTPException.
"""

from dataclasses import dataclass
from typing import Any


# Exceptions applicatives (sans dépendance FastAPI)
class SaisiesAvancesError(Exception):
    """Erreur métier saisies/avances."""

    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class NotFoundError(SaisiesAvancesError):
    """Ressource non trouvée (404)."""

    def __init__(self, message: str = "Ressource non trouvée"):
        super().__init__(message, status_code=404)


class ForbiddenError(SaisiesAvancesError):
    """Action non autorisée (403)."""

    def __init__(self, message: str = "Action non autorisée"):
        super().__init__(message, status_code=403)


class ValidationError(SaisiesAvancesError):
    """Données invalides (400)."""

    def __init__(self, message: str):
        super().__init__(message, status_code=400)


@dataclass(frozen=True)
class UserContext:
    """Contexte utilisateur pour les cas d'usage (sans dépendance au modèle User)."""

    user_id: Any  # str ou UUID
    role: str
