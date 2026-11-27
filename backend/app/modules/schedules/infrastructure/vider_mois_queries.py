"""Lectures du vidage d'un mois : absences validées et bulletins du salarié."""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List

from app.core.database import supabase


def absences_validees_du_salarie(employee_id: str) -> List[Dict[str, Any]]:
    """Demandes d'absence validées du salarié (tous types) : `selected_days`.

    Le type se trie en Python ailleurs : filtrer sur l'enum PostgreSQL fait
    échouer la requête dès qu'un libellé manque (cf. `arrets_valides`).
    """
    resp = (
        supabase.table("absence_requests")
        .select("type, status, selected_days")
        .eq("employee_id", str(employee_id))
        .eq("status", "validated")
        .execute()
    )
    return list(resp.data or [])


def bulletins_du_salarie(employee_id: str, annees: List[int]) -> List[Dict[str, Any]]:
    """Bulletins du salarié pour ces années : mois, statut, origine."""
    resp = (
        supabase.table("payslips")
        .select("year, month, status, origine")
        .eq("employee_id", str(employee_id))
        .in_("year", sorted(set(annees)))
        .execute()
    )
    return list(resp.data or [])


def jours_dans_le_mois(selected_days: Any, debut: date, fin: date) -> set[int]:
    jours: set[int] = set()
    for brut in selected_days or []:
        try:
            d = date.fromisoformat(str(brut)[:10])
        except ValueError:
            continue
        if debut <= d <= fin:
            jours.add(d.day)
    return jours
