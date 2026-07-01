"""Construction payload multi-mois pour import planning / relevé."""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Any, Dict, List, Sequence, Tuple

from app.modules.schedules.application.employee_match import resolve_employee_for_timesheet
from app.modules.schedules.application.timesheet_import.structured_parser import TabularDayRow
from app.modules.schedules.schemas.ai import AiDayEntry, RosterEmployee


def row_date(row: TabularDayRow) -> date | None:
    if not row.jour or not row.month or not row.year:
        return None
    try:
        return date(row.year, row.month, row.jour)
    except ValueError:
        return None


def unique_months_in_rows(rows: Sequence[TabularDayRow]) -> List[Tuple[int, int]]:
    months = sorted({(d.year, d.month) for r in rows if (d := row_date(r))})
    return months


def pick_anchor_month(rows: Sequence[TabularDayRow]) -> Tuple[int, int]:
    counts: Dict[Tuple[int, int], int] = defaultdict(int)
    for row in rows:
        d = row_date(row)
        if d:
            counts[(d.year, d.month)] += 1
    if counts:
        return max(counts.items(), key=lambda item: item[1])[0]
    if rows:
        return rows[0].year or 2026, rows[0].month or 1
    return 2026, 1


_STATUS_RANK = {"ok": 3, "warning": 2, "error": 1, "empty": 0}


def _dedupe_group_employees(emps: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Empêche qu'un même employee_id soit rapproché deux fois dans le même
    groupe mois (deux raw_name distincts matchés au même salarié)."""
    by_employee: Dict[str, List[int]] = defaultdict(list)
    for idx, emp in enumerate(emps):
        if emp.get("employee_id"):
            by_employee[emp["employee_id"]].append(idx)

    for indices in by_employee.values():
        if len(indices) < 2:
            continue
        best_idx = max(
            indices,
            key=lambda i: (
                _STATUS_RANK.get(emps[i].get("review_status") or "error", 0),
                len(emps[i].get("days") or []),
            ),
        )
        winner_name = emps[best_idx].get("raw_name")
        for idx in indices:
            if idx == best_idx:
                continue
            emps[idx]["employee_id"] = None
            emps[idx]["review_status"] = "error"
            emps[idx].setdefault("warnings", []).append(
                f"Même salarié que « {winner_name} » — associez manuellement le bon salarié."
            )
    return emps


def build_month_groups_from_rows(
    rows: Sequence[TabularDayRow],
    roster: List[RosterEmployee],
) -> List[Dict[str, Any]]:
    by_month_emp: Dict[Tuple[int, int, str], List[TabularDayRow]] = defaultdict(list)
    for row in rows:
        d = row_date(row)
        if not d:
            continue
        key = row.matricule or row.raw_name or f"row_{row.jour}"
        by_month_emp[(d.year, d.month, key)].append(row)

    groups_map: Dict[Tuple[int, int], List[Dict[str, Any]]] = defaultdict(list)
    for (year, month, _emp_key), emp_rows in sorted(by_month_emp.items()):
        sample = emp_rows[0]
        raw_name = sample.raw_name or _emp_key
        proposal = resolve_employee_for_timesheet(
            raw_name=raw_name,
            matricule=sample.matricule,
            roster=roster,
        )
        days = [
            AiDayEntry(
                jour=r.jour,
                heures=r.heures,
                type="travail",
                nature="reel",
                punch_entry_raw=str(r.entry_raw) if r.entry_raw is not None else None,
                punch_exit_raw=str(r.exit_raw) if r.exit_raw is not None else None,
                shift_code=r.shift_code,
            )
            for r in emp_rows
        ]
        groups_map[(year, month)].append(
            {
                "employee_id": proposal.employee_id,
                "raw_name": raw_name,
                "time_tracking_id": sample.matricule,
                "review_status": proposal.review_status,
                "days": [d.model_dump(mode="json") for d in days],
            }
        )

    return [
        {"year": y, "month": m, "employees": _dedupe_group_employees(emps)}
        for (y, m), emps in sorted(groups_map.items())
    ]


__all__ = [
    "build_month_groups_from_rows",
    "pick_anchor_month",
    "row_date",
    "unique_months_in_rows",
]
