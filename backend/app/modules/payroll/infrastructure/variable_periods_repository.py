"""Accès à `company_variable_periods` — la fenêtre des variables d'un mois."""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Any

from postgrest.exceptions import APIError

from app.core.database import supabase

TABLE = "company_variable_periods"
logger = logging.getLogger(__name__)

# Code PostgREST « relation inconnue » : la migration n'est pas passée sur cette base.
_CODE_TABLE_ABSENTE = "PGRST205"


def _table_absente(exc: APIError) -> bool:
    return str(getattr(exc, "code", "") or "") == _CODE_TABLE_ABSENTE


def get_variable_period(company_id: str, annee: int, mois: int) -> dict[str, Any] | None:
    """La surcharge du mois, ou None si la règle société s'applique.

    Une base où la table n'existe pas encore (migration non appliquée)
    équivaut à « aucune surcharge » : la génération d'un bulletin ne doit
    pas tomber pour une table facultative de paramétrage.
    """
    try:
        resp = (
            supabase.table(TABLE)
            .select("*")
            .match({"company_id": str(company_id), "year": int(annee), "month": int(mois)})
            .maybe_single()
            .execute()
        )
    except APIError as exc:
        if _table_absente(exc):
            logger.warning("Table %s absente : la règle société s'applique", TABLE)
            return None
        raise
    return resp.data if resp and resp.data else None


def list_variable_periods(company_id: str, annee: int) -> list[dict[str, Any]]:
    """Toutes les surcharges d'une année, pour l'affichage société."""
    resp = (
        supabase.table(TABLE)
        .select("*")
        .match({"company_id": str(company_id), "year": int(annee)})
        .order("month")
        .execute()
    )
    return (resp.data if resp else None) or []


def upsert_variable_period(
    company_id: str,
    annee: int,
    mois: int,
    debut: date,
    fin: date,
    origine: str,
    user_id: str | None = None,
) -> dict[str, Any]:
    """Pose ou remplace la fenêtre du mois."""
    payload = {
        "company_id": str(company_id),
        "year": int(annee),
        "month": int(mois),
        "start_date": debut.isoformat(),
        "end_date": fin.isoformat(),
        "origin": origine,
        "created_by": str(user_id) if user_id else None,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    resp = (
        supabase.table(TABLE)
        .upsert(payload, on_conflict="company_id,year,month")
        .execute()
    )
    rows = (resp.data if resp else None) or []
    return rows[0] if rows else payload


__all__ = [
    "get_variable_period",
    "list_variable_periods",
    "upsert_variable_period",
]
