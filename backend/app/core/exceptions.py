"""
Exceptions transverses de l'application.

Hiérarchie minimale pour les gestionnaires d'erreurs (app/api/error_handlers).
Aucune logique métier ; compatible avec HTTPException FastAPI.
"""
from __future__ import annotations


class AppException(Exception):
    """Exception de base pour l'application. Peut porter un code HTTP et un détail."""

    def __init__(
        self,
        message: str = "Erreur application",
        status_code: int = 500,
        detail: str | None = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.detail = detail or message


class NotFoundError(AppException):
    """Ressource non trouvée (404)."""

    def __init__(self, message: str = "Ressource non trouvée", detail: str | None = None):
        super().__init__(message=message, status_code=404, detail=detail)


class ForbiddenError(AppException):
    """Accès refusé (403)."""

    def __init__(self, message: str = "Accès refusé", detail: str | None = None):
        super().__init__(message=message, status_code=403, detail=detail)


class UnauthorizedError(AppException):
    """Non authentifié (401)."""

    def __init__(self, message: str = "Non authentifié", detail: str | None = None):
        super().__init__(message=message, status_code=401, detail=detail)


class ValidationError(AppException):
    """Erreur de validation (422)."""

    def __init__(self, message: str = "Données invalides", detail: str | None = None):
        super().__init__(message=message, status_code=422, detail=detail)
