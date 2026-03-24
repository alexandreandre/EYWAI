# app/modules/medical_follow_up/domain/rules.py
"""
Règles métier pures du suivi médical : calcul des KPIs à partir de lignes.

Aucune I/O, aucun FastAPI. Utilisé par l’infrastructure (repository) après lecture DB.
"""

from datetime import date, timedelta
from typing import Any, Dict, List


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
