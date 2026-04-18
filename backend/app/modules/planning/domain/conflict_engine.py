"""
Moteur de détection de conflits Planning (pur Python, sans FastAPI ni DB).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class ConflictResult:
    has_blocking_conflict: bool
    is_warning_only: bool
    conflict_type: str
    message: str
    details: Dict[str, Any] = field(default_factory=dict)


def _norm_date_str(d: str) -> str:
    return (d or "")[:10]


def _parse_time_loose(value: Any) -> Optional[time]:
    if value is None:
        return None
    if isinstance(value, time):
        return value
    if isinstance(value, str):
        s = value.strip()
        if len(s) >= 8 and s[2] == ":" and s[5] == ":":
            s = s[:8]
        parts = s.split(":")
        if len(parts) < 2:
            return None
        h = int(parts[0])
        m = int(parts[1])
        sec = int(parts[2]) if len(parts) > 2 else 0
        return time(h, m, sec)
    return None


def _parse_shift_date(value: Any) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return date.fromisoformat(value[:10])
    return None


def _shift_interval_on_timeline(
    shift_date: date, start_t: time, end_t: time
) -> Tuple[datetime, datetime]:
    start_dt = datetime.combine(shift_date, start_t)
    end_dt = datetime.combine(shift_date, end_t)
    if end_dt <= start_dt:
        end_dt += timedelta(days=1)
    return start_dt, end_dt


def _shift_duration_minutes(row: Dict[str, Any]) -> int:
    if row.get("transverse_category") is not None:
        return 0
    sd = _parse_shift_date(row.get("shift_date"))
    st = _parse_time_loose(row.get("start_time"))
    et = _parse_time_loose(row.get("end_time"))
    if sd is None or st is None or et is None:
        return 0
    a, b = _shift_interval_on_timeline(sd, st, et)
    return int((b - a).total_seconds() // 60)


def _format_hm(t: time) -> str:
    return t.strftime("%H:%M")


def check_absence_conflict(
    shift_date: str,
    existing_absences: List[dict],
) -> ConflictResult:
    """Vérifie si shift_date tombe sur un jour d'absence validée (selected_days)."""
    target = _norm_date_str(shift_date)
    for row in existing_absences:
        days = row.get("selected_days") or []
        days_as_str = [str(d)[:10] for d in days]
        if target in days_as_str:
            return ConflictResult(
                has_blocking_conflict=True,
                is_warning_only=False,
                conflict_type="absence_conflict",
                message=(
                    "Le salarié est en absence ce jour (congé validé). "
                    "Annulez l'absence ou choisissez une autre date."
                ),
                details={
                    "absence_type": row.get("type"),
                    "absence_date": target,
                },
            )
    return ConflictResult(
        has_blocking_conflict=False,
        is_warning_only=False,
        conflict_type="no_conflict",
        message="",
        details={},
    )


def check_shift_overlap(
    new_start: str,
    new_end: str,
    existing_shifts: List[dict],
    exclude_shift_id: Optional[str] = None,
) -> ConflictResult:
    """
    Chevauchement si new_start < existing.end et new_end > existing.start
    (même jour ; shifts passant minuit : fin sur le jour suivant).
    """
    if not existing_shifts:
        return ConflictResult(
            has_blocking_conflict=False,
            is_warning_only=False,
            conflict_type="no_conflict",
            message="",
            details={},
        )
    ref_date = _parse_shift_date(existing_shifts[0].get("shift_date")) or date.min
    ns = _parse_time_loose(new_start)
    ne = _parse_time_loose(new_end)
    if ns is None or ne is None:
        return ConflictResult(
            has_blocking_conflict=False,
            is_warning_only=False,
            conflict_type="no_conflict",
            message="",
            details={},
        )
    n0, n1 = _shift_interval_on_timeline(ref_date, ns, ne)

    for ex in existing_shifts:
        eid = ex.get("id")
        if exclude_shift_id is not None and str(eid or "") == str(exclude_shift_id):
            continue
        sd = _parse_shift_date(ex.get("shift_date")) or ref_date
        st = _parse_time_loose(ex.get("start_time"))
        et = _parse_time_loose(ex.get("end_time"))
        if st is None or et is None:
            continue
        e0, e1 = _shift_interval_on_timeline(sd, st, et)
        if n0 < e1 and n1 > e0:
            return ConflictResult(
                has_blocking_conflict=True,
                is_warning_only=False,
                conflict_type="shift_overlap",
                message=(
                    f"Ce salarié a déjà un shift de {_format_hm(st)} à {_format_hm(et)} "
                    "ce jour."
                ),
                details={
                    "conflicting_shift_id": eid,
                    "conflicting_start": str(ex.get("start_time")),
                    "conflicting_end": str(ex.get("end_time")),
                },
            )
    return ConflictResult(
        has_blocking_conflict=False,
        is_warning_only=False,
        conflict_type="no_conflict",
        message="",
        details={},
    )


def _merge_intervals(
    intervals: List[Tuple[datetime, datetime]],
) -> List[Tuple[datetime, datetime]]:
    if not intervals:
        return []
    intervals = sorted(intervals, key=lambda x: x[0])
    merged: List[Tuple[datetime, datetime]] = [intervals[0]]
    for cur_s, cur_e in intervals[1:]:
        last_s, last_e = merged[-1]
        if cur_s <= last_e:
            merged[-1] = (last_s, max(last_e, cur_e))
        else:
            merged.append((cur_s, cur_e))
    return merged


def check_weekly_rest(
    week_shifts: List[dict],
    min_rest_hours: int = 35,
) -> ConflictResult:
    """Repère le plus long créneau sans shift sur la semaine ISO (lun→dim)."""
    dates: List[date] = []
    for s in week_shifts:
        d = _parse_shift_date(s.get("shift_date"))
        if d:
            dates.append(d)
    if not dates:
        return ConflictResult(
            has_blocking_conflict=False,
            is_warning_only=False,
            conflict_type="no_conflict",
            message="",
            details={},
        )
    min_d = min(dates)
    monday = min_d - timedelta(days=min_d.weekday())
    week_start = datetime.combine(monday, time(0, 0, 0))
    week_end = week_start + timedelta(days=7)

    intervals: List[Tuple[datetime, datetime]] = []
    for s in week_shifts:
        sd = _parse_shift_date(s.get("shift_date"))
        st = _parse_time_loose(s.get("start_time"))
        et = _parse_time_loose(s.get("end_time"))
        if sd is None or st is None or et is None:
            continue
        intervals.append(_shift_interval_on_timeline(sd, st, et))

    merged = _merge_intervals(intervals)
    max_rest_hours = 0.0

    if not merged:
        max_rest_hours = (week_end - week_start).total_seconds() / 3600.0
    else:
        gap = (merged[0][0] - week_start).total_seconds() / 3600.0
        max_rest_hours = max(max_rest_hours, gap)
        for i in range(len(merged) - 1):
            gap = (merged[i + 1][0] - merged[i][1]).total_seconds() / 3600.0
            max_rest_hours = max(max_rest_hours, gap)
        gap = (week_end - merged[-1][1]).total_seconds() / 3600.0
        max_rest_hours = max(max_rest_hours, gap)

    if max_rest_hours < float(min_rest_hours):
        return ConflictResult(
            has_blocking_conflict=False,
            is_warning_only=True,
            conflict_type="weekly_rest_violation",
            message=(
                f"Le repos hebdomadaire de {min_rest_hours} h n'est pas respecté.\n"
                "Confirmer malgré tout ?"
            ),
            details={
                "max_rest_hours": round(max_rest_hours, 2),
                "required_hours": min_rest_hours,
            },
        )
    return ConflictResult(
        has_blocking_conflict=False,
        is_warning_only=False,
        conflict_type="no_conflict",
        message="",
        details={},
    )


def check_contract_overtime(
    week_shifts: List[dict],
    contract_hours_per_week: float,
) -> ConflictResult:
    """Total heures planifiées (hors transverse) vs contrat."""
    total_minutes = sum(_shift_duration_minutes(s) for s in week_shifts)
    contract_minutes = int(round(float(contract_hours_per_week) * 60))
    if total_minutes <= contract_minutes:
        return ConflictResult(
            has_blocking_conflict=False,
            is_warning_only=False,
            conflict_type="no_conflict",
            message="",
            details={},
        )
    delta_minutes = total_minutes - contract_minutes
    delta_h = delta_minutes // 60
    delta_m = delta_minutes % 60
    return ConflictResult(
        has_blocking_conflict=False,
        is_warning_only=True,
        conflict_type="contract_overtime",
        message=f"+{delta_h}h{delta_m:02d} au-delà du contrat hebdomadaire",
        details={
            "total_minutes": total_minutes,
            "contract_minutes": contract_minutes,
            "delta_minutes": delta_minutes,
        },
    )


def run_all_checks(
    shift_date: str,
    new_start: str,
    new_end: str,
    existing_absences: List[dict],
    existing_day_shifts: List[dict],
    week_shifts: List[dict],
    contract_hours_per_week: float,
    exclude_shift_id: Optional[str] = None,
    min_rest_hours: int = 35,
) -> List[ConflictResult]:
    """Enchaîne les 4 contrôles ; s'arrête au premier conflit bloquant."""
    results: List[ConflictResult] = []

    r1 = check_absence_conflict(shift_date, existing_absences)
    results.append(r1)
    if r1.has_blocking_conflict:
        return results

    r2 = check_shift_overlap(
        new_start, new_end, existing_day_shifts, exclude_shift_id=exclude_shift_id
    )
    results.append(r2)
    if r2.has_blocking_conflict:
        return results

    r3 = check_weekly_rest(week_shifts, min_rest_hours=min_rest_hours)
    results.append(r3)

    r4 = check_contract_overtime(week_shifts, contract_hours_per_week)
    results.append(r4)

    return results
