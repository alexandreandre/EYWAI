"""Traduction des erreurs PostgREST liées au schéma badgeuse."""

from __future__ import annotations

from fastapi import HTTPException, status
from postgrest.exceptions import APIError

from app.core.supabase_resilience import execute_with_retry, is_transient_supabase_error

_BADGEUSE_TABLES = (
    "employee_time_entries",
    "employee_time_entries_validations",
    "employee_badge_credentials",
)

_MIGRATION_HINT = (
    "Tables badgeuse absentes sur Supabase. "
    "Exécutez la migration `supabase/migrations/20260525120000_badgeuse_qr.sql` "
    "(SQL Editor du projet ou `python backend/scripts/check_badgeuse_schema.py`)."
)


def is_missing_badgeuse_schema(exc: APIError) -> bool:
    if exc.code != "PGRST205":
        return False
    message = str(exc.message or "")
    return any(table in message for table in _BADGEUSE_TABLES)


def raise_if_missing_badgeuse_schema(exc: APIError) -> None:
    """Relève une HTTP 503 explicite si le schéma badgeuse n'est pas déployé."""
    if is_missing_badgeuse_schema(exc):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_MIGRATION_HINT,
        ) from exc
    raise exc


def execute_supabase(callable_query):
    """Exécute une requête Supabase (retry réseau) et traduit PGRST205 (tables manquantes)."""
    try:
        return execute_with_retry(callable_query)
    except APIError as exc:
        raise_if_missing_badgeuse_schema(exc)
    except Exception as exc:
        if is_transient_supabase_error(exc):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    "Connexion à la base temporairement indisponible. "
                    "Réessayez dans quelques secondes."
                ),
            ) from exc
        raise
