"""
Dépendances et helpers HTTP partagés pour les routers FastAPI.

Réduit la duplication de _require_active_company / _handle_application_errors.
"""

from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar

from fastapi import HTTPException

from app.core.errors import AppError, ForbiddenError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.core.platform_admin import is_platform_admin
from app.modules.users.schemas.responses import User

logger = get_logger("core.http_dependencies")

F = TypeVar("F", bound=Callable[..., Any])


def require_active_company(user: User) -> str:
    """Retourne company_id active ou lève HTTP 400."""
    company_id = user.active_company_id
    if not company_id:
        raise HTTPException(status_code=400, detail="Aucune entreprise active.")
    return str(company_id)


def require_rh_access(user: User, company_id: str) -> None:
    """Vérifie droits RH sur l'entreprise (ou admin plateforme)."""
    if is_platform_admin(user):
        return
    if not user.has_rh_access_in_company(str(company_id)):
        raise HTTPException(
            status_code=403,
            detail="Accès RH requis pour cette opération.",
        )


def map_application_exception(exc: Exception) -> HTTPException:
    """Convertit une exception métier en HTTPException."""
    if isinstance(exc, HTTPException):
        return exc
    if isinstance(exc, NotFoundError):
        return HTTPException(status_code=404, detail=exc.message)
    if isinstance(exc, ForbiddenError):
        return HTTPException(status_code=403, detail=exc.message)
    if isinstance(exc, ValidationError):
        return HTTPException(status_code=400, detail=exc.message)
    if isinstance(exc, AppError):
        return HTTPException(status_code=400, detail=exc.message)
    if isinstance(exc, LookupError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, PermissionError):
        return HTTPException(status_code=403, detail=str(exc))
    if isinstance(exc, ValueError):
        return HTTPException(status_code=400, detail=str(exc))
    logger.exception("Erreur non gérée")
    return HTTPException(status_code=500, detail=str(exc))


def handle_router_errors(fn: F) -> F:
    """Décorateur : capture les exceptions et les mappe en réponses HTTP."""

    @wraps(fn)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return await fn(*args, **kwargs)
        except HTTPException:
            raise
        except Exception as exc:
            raise map_application_exception(exc) from exc

    return wrapper  # type: ignore[misc]
