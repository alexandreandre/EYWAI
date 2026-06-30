"""Rapprochement manuel feuille Excel → salarié pour import calendrier."""

from __future__ import annotations

from typing import Any, Dict, List

from collections import defaultdict

from app.modules.admin_import.application.planning_import_summary import (
    build_planning_import_summary,
)
from app.modules.admin_import.infrastructure import repository as repo
from app.modules.schedules.application.employee_match import rank_planning_sheet_candidates
from app.modules.schedules.application.exceptions import ScheduleAppError
from app.modules.schedules.infrastructure.timesheet_import_repository import (
    timesheet_import_repository,
)
from app.modules.schedules.schemas.ai import RosterEmployee


def _normalize_sheet_name(name: str) -> str:
    from app.modules.schedules.application.planning_import.quadra_calendar import (
        _sheet_key,
    )

    return _sheet_key(name)


def _assigned_by_sheet(month_groups: List[Dict[str, Any]]) -> Dict[str, str]:
    assigned: Dict[str, str] = {}
    for group in month_groups:
        for emp in group.get("employees") or []:
            raw = str(emp.get("raw_name") or "")
            employee_id = emp.get("employee_id")
            if raw and employee_id:
                assigned[_normalize_sheet_name(raw)] = str(employee_id)
    return assigned


def _refresh_sheet_suggestions(
    month_groups: List[Dict[str, Any]],
    roster: List[RosterEmployee],
    used_employee_ids: set[str],
) -> None:
    rows_by_norm: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    sheet_meta: Dict[str, Dict[str, Any]] = {}
    for group in month_groups:
        for emp in group.get("employees") or []:
            raw = str(emp.get("raw_name") or "")
            norm = _normalize_sheet_name(raw)
            if not raw:
                continue
            rows_by_norm[norm].append(emp)
            if norm not in sheet_meta:
                sheet_meta[norm] = {
                    "raw_name": raw,
                    "sommaire_hint": str(emp.get("sommaire_hint") or "") or None,
                }

    for norm, meta in sheet_meta.items():
        suggestions = rank_planning_sheet_candidates(
            meta["raw_name"],
            roster,
            exclude_employee_ids=used_employee_ids,
            hint_name=meta["sommaire_hint"],
            limit=5,
        )
        suggestion_ids = [e.id for e in suggestions]
        for row in rows_by_norm[norm]:
            if row.get("employee_id"):
                continue
            row["suggested_employee_ids"] = suggestion_ids


def apply_planning_manual_mappings(
    batch_id: str,
    company_id: str,
    mappings: List[Dict[str, str]],
) -> Dict[str, Any]:
    if not mappings:
        raise ValueError("Aucun rapprochement fourni.")

    batch = timesheet_import_repository.get_batch(batch_id, company_id=company_id)
    if not batch:
        raise LookupError("Batch introuvable.")
    status = str(batch.get("status") or "")
    if status not in ("previewed", "parsed"):
        raise ScheduleAppError(
            "validation",
            "Ce batch ne peut plus être modifié.",
            status_code=409,
        )

    summary = dict(batch.get("summary_json") or {})
    month_groups = list(summary.get("month_groups") or [])
    if not month_groups:
        raise ScheduleAppError(
            "validation",
            "Rapprochement manuel indisponible pour ce type de fichier.",
            status_code=422,
        )

    employees = repo.list_company_employees(company_id)
    emp_by_id = {str(row["id"]): row for row in employees}
    mapping_by_norm: Dict[str, str] = {}
    target_employee_ids: set[str] = set()
    for item in mappings:
        raw_name = str(item.get("raw_name") or "").strip()
        employee_id = str(item.get("employee_id") or "").strip()
        if not raw_name or not employee_id:
            continue
        if employee_id not in emp_by_id:
            raise ScheduleAppError(
                "validation",
                f"Salarié introuvable dans l'entreprise ({employee_id}).",
                status_code=422,
            )
        if employee_id in target_employee_ids:
            raise ScheduleAppError(
                "validation",
                "Ce salarié est déjà sélectionné pour une autre feuille Excel.",
                status_code=422,
            )
        target_employee_ids.add(employee_id)
        mapping_by_norm[_normalize_sheet_name(raw_name)] = employee_id

    if not mapping_by_norm:
        raise ValueError("Rapprochements invalides.")

    current_assigned = _assigned_by_sheet(month_groups)
    for raw_norm, employee_id in mapping_by_norm.items():
        for other_norm, other_id in current_assigned.items():
            if other_id == employee_id:
                raise ScheduleAppError(
                    "validation",
                    "Ce salarié est déjà associé à une feuille Excel.",
                    status_code=422,
                )

    roster = [
        RosterEmployee(
            id=str(row["id"]),
            first_name=str(row.get("first_name") or ""),
            last_name=str(row.get("last_name") or ""),
            time_tracking_id=row.get("time_tracking_id"),
        )
        for row in employees
    ]

    for group in month_groups:
        for emp in group.get("employees") or []:
            raw = str(emp.get("raw_name") or "")
            employee_id = mapping_by_norm.get(_normalize_sheet_name(raw))
            if not employee_id:
                continue
            row = emp_by_id[employee_id]
            emp["employee_id"] = employee_id
            emp["matched_name"] = (
                f"{row.get('first_name') or ''} {row.get('last_name') or ''}".strip()
            )
            emp["review_status"] = "ok"
            emp["match_method"] = "name_exact"
            emp["match_confidence"] = "high"

    unmatched: List[str] = []
    seen_sheets: set[str] = set()
    for group in month_groups:
        for emp in group.get("employees") or []:
            raw = str(emp.get("raw_name") or "")
            if not raw or raw in seen_sheets:
                continue
            seen_sheets.add(raw)
            if not emp.get("employee_id"):
                unmatched.append(raw)

    used_employee_ids = {
        str(emp["employee_id"])
        for group in month_groups
        for emp in group.get("employees") or []
        if emp.get("employee_id")
    }
    _refresh_sheet_suggestions(month_groups, roster, used_employee_ids)

    summary["month_groups"] = month_groups
    summary["sheets_unmatched"] = unmatched

    preview_old = batch.get("preview_json") or {}
    timesheet_import_repository.update_batch(batch_id, {"summary_json": summary})

    period_mode = str(summary.get("period_mode") or "year")
    new_summary = build_planning_import_summary(
        preview=preview_old,
        batch_summary=summary,
        parser_key=batch.get("parser_key"),
        period_mode=period_mode,
        year=int(batch.get("period_year") or preview_old.get("year") or 2026),
        month=int(batch.get("period_month") or preview_old.get("month") or 1),
    )
    return {"batch_id": batch_id, "summary": new_summary}


__all__ = ["apply_planning_manual_mappings"]
