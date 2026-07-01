# app/modules/medical_follow_up/domain/rules.py
"""
Règles métier pures du suivi médical : calcul des KPIs à partir de lignes.

Aucune I/O, aucun FastAPI. Utilisé par l’infrastructure (repository) après lecture DB.
"""

from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Sequence


def birth_at_age(birth_date: date, years: int) -> date:
    """Date du N-ième anniversaire (gère 29 février → 28 février)."""
    try:
        return birth_date.replace(year=birth_date.year + years)
    except ValueError:
        return birth_date.replace(year=birth_date.year + years, day=28)


def _birth_at_age(birth_date: date, years: int) -> date:
    return birth_at_age(birth_date, years)


def _has_visit_on_or_after(
    visit_dates: Sequence[date], threshold: date
) -> bool:
    return any(d >= threshold for d in visit_dates)


def should_require_aptitude_sir(
    hire_date: Optional[date],
    completed_sir_dates: Sequence[date],
) -> bool:
    """
    Aptitude SIR avant affectation : requise seulement si aucune visite SIR réalisée.
    Dès qu'un suivi SIR périodique existe (registre SPST), l'aptitude initiale est obsolète.
    """
    if hire_date is None:
        return False
    if completed_sir_dates:
        return False
    return True


def should_require_mi_carriere(
    birth_date: Optional[date],
    completed_sir_dates: Sequence[date],
    completed_vip_dates: Sequence[date],
    completed_mi_carriere_dates: Sequence[date],
    today: date,
) -> bool:
    """
    Visite mi-carrière (45 ans) : requise seulement si le salarié a 45 ans ou plus
    et qu'aucune visite (SIR, VIP ou mi-carrière) n'a été réalisée depuis les 45 ans.
    """
    if birth_date is None:
        return False
    birth_45 = _birth_at_age(birth_date, 45)
    if today < birth_45:
        return False
    post_45_visits = (
        list(completed_sir_dates)
        + list(completed_vip_dates)
        + list(completed_mi_carriere_dates)
    )
    if post_45_visits and _has_visit_on_or_after(post_45_visits, birth_45):
        return False
    # Suivi périodique VIP/SIR déjà en place : pas de mi-carrière ponctuelle en parallèle.
    if completed_sir_dates or completed_vip_dates:
        return False
    return True


def should_require_vip_periodic(
    is_poste_sir: bool,
    completed_vip_dates: Sequence[date],
) -> bool:
    """
    VIP périodique / à l'embauche : non requise pour un poste SIR (suivi Renforcé).
    """
    if is_poste_sir:
        return False
    return True


def compute_kpis_from_rows(rows: List[Dict[str, Any]], today: date) -> Dict[str, int]:
    """
    Calcule les indicateurs KPIs à partir d’une liste de lignes obligations
    (champs due_date, status, completed_date).

    Comportement identique au legacy (router / application).
    """
    due_30 = (today + timedelta(days=30)).isoformat()
    month_start = today.replace(day=1).isoformat()
    today_iso = today.isoformat()

    overdue = sum(
        1
        for r in rows
        if r.get("status") != "realisee"
        and r.get("due_date")
        and r["due_date"] < today_iso
    )
    due_within_30 = sum(
        1
        for r in rows
        if r.get("status") != "realisee"
        and r.get("due_date")
        and today_iso <= r["due_date"] <= due_30
    )
    active_total = sum(1 for r in rows if r.get("status") != "realisee")
    completed_this_month = sum(
        1
        for r in rows
        if r.get("status") == "realisee"
        and r.get("completed_date")
        and r["completed_date"] >= month_start
    )
    return {
        "overdue_count": overdue,
        "due_within_30_count": due_within_30,
        "active_total": active_total,
        "completed_this_month": completed_this_month,
    }
