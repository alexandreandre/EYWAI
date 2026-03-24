"""
Exceptions métier du module collective_agreements.

Sans dépendance à FastAPI. L'application (service) les convertit en HTTPException.
"""
from __future__ import annotations


class CollectiveAgreementError(Exception):
    """Base pour les erreurs métier du module."""

    def __init__(self, message: str, code: str = "error"):
        self.message = message
        self.code = code
        super().__init__(message)


class NotFoundError(CollectiveAgreementError):
    """Ressource non trouvée (ex. convention, assignation)."""

    def __init__(self, message: str = "Ressource non trouvée"):
        super().__init__(message, code="not_found")


class ForbiddenError(CollectiveAgreementError):
    """Accès refusé (droits insuffisants)."""

    def __init__(self, message: str = "Accès non autorisé"):
        super().__init__(message, code="forbidden")


class ValidationError(CollectiveAgreementError):
    """Données invalides (ex. aucune donnée à mettre à jour)."""

    def __init__(self, message: str = "Données invalides"):
        super().__init__(message, code="validation_error")
