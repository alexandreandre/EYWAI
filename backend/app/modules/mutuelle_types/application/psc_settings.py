"""Paramètres PSC entreprise (mutuelle / prévoyance)."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from app.core.database import supabase


def get_psc_settings(company_id: str) -> dict[str, Any]:
    resp = (
        supabase.table("company_psc_settings")
        .select("*")
        .eq("company_id", company_id)
        .limit(1)
        .execute()
    )
    if resp.data:
        row = resp.data[0]
        return {
            "company_id": company_id,
            "mutuelle_organisme_label": row.get("mutuelle_organisme_label"),
            "mutuelle_employee_self_service": bool(
                row.get("mutuelle_employee_self_service", False)
            ),
        }
    return {
        "company_id": company_id,
        "mutuelle_organisme_label": None,
        "mutuelle_employee_self_service": False,
    }


def upsert_psc_settings(
    company_id: str,
    *,
    mutuelle_organisme_label: str | None = None,
    mutuelle_employee_self_service: bool | None = None,
) -> dict[str, Any]:
    current = get_psc_settings(company_id)
    payload: dict[str, Any] = {
        "company_id": company_id,
        "mutuelle_organisme_label": (
            mutuelle_organisme_label
            if mutuelle_organisme_label is not None
            else current.get("mutuelle_organisme_label")
        ),
        "mutuelle_employee_self_service": (
            mutuelle_employee_self_service
            if mutuelle_employee_self_service is not None
            else current.get("mutuelle_employee_self_service", False)
        ),
    }
    if payload["mutuelle_organisme_label"] is not None:
        payload["mutuelle_organisme_label"] = payload["mutuelle_organisme_label"].strip() or None
    resp = (
        supabase.table("company_psc_settings")
        .upsert(payload, on_conflict="company_id")
        .execute()
    )
    if not resp.data:
        raise HTTPException(
            status_code=500,
            detail="Impossible d'enregistrer les paramètres PSC.",
        )
    row = resp.data[0]
    return {
        "company_id": company_id,
        "mutuelle_organisme_label": row.get("mutuelle_organisme_label"),
        "mutuelle_employee_self_service": bool(
            row.get("mutuelle_employee_self_service", False)
        ),
    }
