"""Traduction des erreurs Postgres / PostgREST en messages API lisibles."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import HTTPException
from postgrest.exceptions import APIError


FK_VIOLATION_MESSAGE = (
    "Impossible de supprimer ce collaborateur : des données liées subsistent encore. "
    "Contactez le support si le problème persiste."
)
GENERIC_DB_MESSAGE = (
    "La suppression a échoué. Réessayez ou contactez le support."
)


def _extract_pg_code(exc: BaseException) -> Optional[str]:
    if isinstance(exc, APIError):
        code = getattr(exc, "code", None)
        if code:
            return str(code)
        details = getattr(exc, "details", None)
        if details and "23503" in str(details):
            return "23503"
        message = str(getattr(exc, "message", "") or exc)
        if "23503" in message:
            return "23503"
    text = str(exc)
    if "23503" in text:
        return "23503"
    return None


def raise_http_for_db_error(
    exc: BaseException,
    *,
    fk_message: str = FK_VIOLATION_MESSAGE,
    generic_message: str = GENERIC_DB_MESSAGE,
) -> None:
    """Relève une HTTPException adaptée ; ne jamais exposer le détail Postgres au client."""
    code = _extract_pg_code(exc)
    if code == "23503":
        raise HTTPException(status_code=409, detail=fk_message) from exc
    raise HTTPException(status_code=500, detail=generic_message) from exc


def is_fk_violation(exc: BaseException) -> bool:
    return _extract_pg_code(exc) == "23503"


def api_error_payload(exc: APIError) -> dict[str, Any]:
    return {
        "code": getattr(exc, "code", None),
        "message": getattr(exc, "message", None),
        "details": getattr(exc, "details", None),
    }
