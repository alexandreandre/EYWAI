"""Règle de verrouillage de l'édition manuelle des bulletins de paie."""

from __future__ import annotations

from datetime import date, timedelta

DEFAULT_CUTOFF_DAY = 15
MIN_CUTOFF_DAY = 1
MAX_CUTOFF_DAY = 28

_MONTH_NAMES = (
    "",
    "janvier",
    "février",
    "mars",
    "avril",
    "mai",
    "juin",
    "juillet",
    "août",
    "septembre",
    "octobre",
    "novembre",
    "décembre",
)


def normalize_cutoff_day(value: int | None) -> int:
    """Borne le jour de coupure entre 1 et 28."""
    if value is None:
        return DEFAULT_CUTOFF_DAY
    try:
        day = int(value)
    except (TypeError, ValueError):
        return DEFAULT_CUTOFF_DAY
    return max(MIN_CUTOFF_DAY, min(MAX_CUTOFF_DAY, day))


def lock_start_date(year: int, month: int, cutoff_day: int) -> date:
    """Date à partir de laquelle l'édition manuelle est bloquée (inclus)."""
    cutoff_day = normalize_cutoff_day(cutoff_day)
    if month == 12:
        return date(year + 1, 1, cutoff_day)
    return date(year, month + 1, cutoff_day)


def manual_edit_allowed_until(year: int, month: int, cutoff_day: int) -> date:
    """Dernier jour (inclus) où l'édition manuelle reste autorisée."""
    return lock_start_date(year, month, cutoff_day) - timedelta(days=1)


def is_payslip_manual_edit_allowed(
    year: int,
    month: int,
    *,
    cutoff_day: int = DEFAULT_CUTOFF_DAY,
    today: date | None = None,
) -> bool:
    """True si l'édition manuelle du bulletin est encore autorisée."""
    reference = today or date.today()
    return reference < lock_start_date(year, month, cutoff_day)


def payslip_manual_edit_block_reason(
    year: int,
    month: int,
    *,
    cutoff_day: int = DEFAULT_CUTOFF_DAY,
    today: date | None = None,
) -> str | None:
    """Message d'erreur si la période est verrouillée, sinon None."""
    if is_payslip_manual_edit_allowed(
        year, month, cutoff_day=cutoff_day, today=today
    ):
        return None
    lock_date = lock_start_date(year, month, cutoff_day)
    period_label = f"{_MONTH_NAMES[month]} {year}".strip()
    lock_month_label = _MONTH_NAMES[lock_date.month]
    return (
        f"L'édition manuelle du bulletin de {period_label} est verrouillée "
        f"depuis le {lock_date.day} {lock_month_label} {lock_date.year}."
    )
