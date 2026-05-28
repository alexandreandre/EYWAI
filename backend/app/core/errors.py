"""
Exceptions applicatives (sans dépendance FastAPI).

Les routers mappent ces erreurs vers des codes HTTP via http_dependencies.
"""

from __future__ import annotations


class AppError(Exception):
    """Erreur applicative générique."""

    def __init__(self, message: str, *, code: str = "app_error") -> None:
        super().__init__(message)
        self.message = message
        self.code = code


class NotFoundError(AppError):
    def __init__(self, message: str = "Ressource introuvable") -> None:
        super().__init__(message, code="not_found")


class ValidationError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code="validation_error")


class ForbiddenError(AppError):
    def __init__(self, message: str = "Accès refusé") -> None:
        super().__init__(message, code="forbidden")
