"""Calcul des retards onboarding (J+x relatif à la date d'embauche)."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional


def parse_hire_date(value: Any) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    s = str(value).strip()
    if not s:
        return None
    if "T" in s:
        s = s.split("T", 1)[0]
    try:
        return date.fromisoformat(s[:10])
    except ValueError:
        return None


def is_task_overdue(
    hire_date: Optional[date],
    due_days: Optional[int],
    is_completed: bool,
    ref: Optional[date] = None,
) -> bool:
    if is_completed or hire_date is None or due_days is None:
        return False
    ref = ref or date.today()
    due = hire_date + timedelta(days=int(due_days))
    return due < ref


def count_overdue_tasks(
    hire_date: Optional[date],
    tasks: List[Dict[str, Any]],
    ref: Optional[date] = None,
) -> int:
    ref = ref or date.today()
    return sum(
        1
        for t in tasks
        if is_task_overdue(
            hire_date,
            t.get("due_days"),
            bool(t.get("is_completed")),
            ref,
        )
    )


def summarize_tasks(tasks: List[Dict[str, Any]]) -> tuple[int, int, float]:
    """Retourne (nb_completed, nb_total, progress_pct)."""
    nb_total = len(tasks)
    nb_completed = sum(1 for t in tasks if t.get("is_completed"))
    progress_pct = (nb_completed / nb_total * 100.0) if nb_total else 0.0
    return nb_completed, nb_total, progress_pct


def days_since_hire(hire_date: Optional[date], ref: Optional[date] = None) -> Optional[int]:
    if hire_date is None:
        return None
    ref = ref or date.today()
    delta = ref - hire_date
    return max(0, delta.days)
