"""Résumé lisible pour l'aperçu import calendrier prévu."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

ReviewStatus = Literal["ok", "warning", "error"]

_STATUS_RANK = {"ok": 0, "warning": 1, "error": 2}

_FORMAT_LABELS = {
    "quadra_planning_calendar": "Calendrier Quadra (Excel, 1 feuille / salarié)",
    "tabular_generic": "Tableur générique",
    "tabular_punch_pairs": "Tableur pointages",
}

_MONTHS_FR = (
    "",
    "Janvier",
    "Février",
    "Mars",
    "Avril",
    "Mai",
    "Juin",
    "Juillet",
    "Août",
    "Septembre",
    "Octobre",
    "Novembre",
    "Décembre",
)


def _month_label(month: int, year: int) -> str:
    if 1 <= month <= 12:
        return f"{_MONTHS_FR[month]} {year}"
    return f"{month}/{year}"


def _worst_status(a: ReviewStatus, b: ReviewStatus) -> ReviewStatus:
    return a if _STATUS_RANK[a] >= _STATUS_RANK[b] else b


def _employees_from_month_groups(
    month_groups: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    by_key: Dict[str, Dict[str, Any]] = {}
    for group in month_groups:
        for emp in group.get("employees") or []:
            key = str(emp.get("raw_name") or emp.get("employee_id") or "?")
            status = str(emp.get("review_status") or "ok")
            if status not in _STATUS_RANK:
                status = "ok"
            row = by_key.get(key)
            if not row:
                by_key[key] = {
                    "raw_name": str(emp.get("raw_name") or key),
                    "employee_id": emp.get("employee_id"),
                    "matched_name": emp.get("matched_name"),
                    "review_status": status,
                }
                continue
            row["review_status"] = _worst_status(
                row["review_status"], status  # type: ignore[arg-type]
            )
            if emp.get("employee_id") and not row.get("employee_id"):
                row["employee_id"] = emp.get("employee_id")
            if emp.get("matched_name") and not row.get("matched_name"):
                row["matched_name"] = emp.get("matched_name")
    return sorted(by_key.values(), key=lambda r: r["raw_name"].lower())


def _employees_from_preview(preview: Dict[str, Any]) -> List[Dict[str, Any]]:
    by_key: Dict[str, Dict[str, Any]] = {}
    for emp in preview.get("employees") or []:
        key = str(emp.get("employee_id") or emp.get("raw_name") or "?")
        status = str(emp.get("review_status") or "ok")
        if status not in _STATUS_RANK:
            status = "ok"
        row = by_key.get(key)
        if not row:
            by_key[key] = {
                "raw_name": str(emp.get("raw_name") or key),
                "employee_id": emp.get("employee_id"),
                "matched_name": emp.get("matched_name"),
                "review_status": status,
            }
            continue
        row["review_status"] = _worst_status(
            row["review_status"], status  # type: ignore[arg-type]
        )
    return sorted(by_key.values(), key=lambda r: r["raw_name"].lower())


def _count_days(
    *,
    month_groups: List[Dict[str, Any]],
    preview: Optional[Dict[str, Any]],
) -> int:
    if month_groups:
        total = 0
        for group in month_groups:
            for emp in group.get("employees") or []:
                if emp.get("employee_id") or emp.get("review_status") != "error":
                    total += len(emp.get("days") or [])
        return total
    if preview:
        return sum(len(emp.get("days") or []) for emp in preview.get("employees") or [])
    return 0


def _sheet_metadata_from_month_groups(
    month_groups: List[Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    meta: Dict[str, Dict[str, Any]] = {}
    for group in month_groups:
        for emp in group.get("employees") or []:
            raw = str(emp.get("raw_name") or "")
            if not raw or raw in meta:
                continue
            meta[raw] = {
                "suggested_employee_ids": list(emp.get("suggested_employee_ids") or []),
                "sommaire_hint": emp.get("sommaire_hint"),
            }
    return meta


def build_planning_import_summary(
    *,
    preview: Optional[Dict[str, Any]],
    batch_summary: Dict[str, Any],
    parser_key: Optional[str],
    period_mode: str,
    year: int,
    month: int,
) -> Dict[str, Any]:
    month_groups = list(batch_summary.get("month_groups") or [])
    employees = (
        _employees_from_month_groups(month_groups)
        if month_groups
        else _employees_from_preview(preview or {})
    )

    ok = [e for e in employees if e["review_status"] == "ok" and e.get("employee_id")]
    warning = [
        e for e in employees if e["review_status"] == "warning" and e.get("employee_id")
    ]
    error = [e for e in employees if e["review_status"] == "error" or not e.get("employee_id")]
    importable = ok + warning
    assigned_employee_ids = sorted(
        {str(e["employee_id"]) for e in employees if e.get("employee_id")}
    )
    sheet_meta = _sheet_metadata_from_month_groups(month_groups)

    affected = (preview or {}).get("affected_months") or []
    if affected:
        first, last = affected[0], affected[-1]
        period_label = (
            f"{_month_label(int(first['month']), int(first['year']))}"
            f" → {_month_label(int(last['month']), int(last['year']))}"
        )
        months_count = len(affected)
    elif period_mode == "year":
        period_label = f"Année {year} (12 mois)"
        months_count = 12
    elif period_mode == "month":
        period_label = _month_label(month, year)
        months_count = 1
    else:
        period_label = f"Période {year}"
        months_count = batch_summary.get("months_count") or len(month_groups) or 1

    if error and not importable:
        validation_status: ReviewStatus = "error"
    elif error or warning:
        validation_status = "warning"
    else:
        validation_status = "ok"

    unmatched_sheets = list(batch_summary.get("sheets_unmatched") or [])
    review_items: List[Dict[str, Any]] = []
    for emp in warning:
        meta = sheet_meta.get(emp["raw_name"], {})
        review_items.append(
            {
                "raw_name": emp["raw_name"],
                "employee_id": emp.get("employee_id"),
                "matched_name": emp.get("matched_name"),
                "review_status": "warning",
                "needs_manual_match": not emp.get("employee_id"),
                "suggested_employee_ids": meta.get("suggested_employee_ids") or [],
                "sommaire_hint": meta.get("sommaire_hint"),
                "message": (
                    f"Rapprochement approximatif → {emp.get('matched_name') or 'à confirmer'}"
                    if emp.get("matched_name") or emp.get("employee_id")
                    else "Rapprochement incertain — choisissez le salarié"
                ),
            }
        )
    for emp in error:
        meta = sheet_meta.get(emp["raw_name"], {})
        review_items.append(
            {
                "raw_name": emp["raw_name"],
                "employee_id": emp.get("employee_id"),
                "matched_name": emp.get("matched_name"),
                "review_status": "error",
                "needs_manual_match": True,
                "suggested_employee_ids": meta.get("suggested_employee_ids") or [],
                "sommaire_hint": meta.get("sommaire_hint"),
                "message": "Associez cette feuille à un salarié du dossier",
            }
        )

    warnings = list((preview or {}).get("warnings") or [])
    if batch_summary.get("reimport"):
        warnings.insert(
            0,
            "Ce fichier a déjà été enregistré une fois : un nouvel enregistrement "
            "mettra à jour les calendriers prévus existants.",
        )

    return {
        "validation_status": validation_status,
        "ready_to_commit": len(importable) > 0,
        "format_label": _FORMAT_LABELS.get(parser_key or "", parser_key or "Fichier structuré"),
        "period_label": period_label,
        "months_count": months_count,
        "days_total": _count_days(month_groups=month_groups, preview=preview),
        "sheets_parsed": batch_summary.get("sheets_parsed"),
        "employees_total": len(employees),
        "employees_ok": len(ok),
        "employees_warning": len(warning),
        "employees_error": len(error),
        "employees_importable": len(importable),
        "assigned_employee_ids": assigned_employee_ids,
        "unmatched_sheets": unmatched_sheets,
        "review_items": review_items[:20],
        "review_items_truncated": max(0, len(review_items) - 20),
        "warnings": warnings[:5],
        "commit_hint": _commit_hint(validation_status, len(importable), len(error)),
    }


def _commit_hint(status: ReviewStatus, importable: int, errors: int) -> str:
    if importable == 0:
        return "Aucun salarié importable — corrigez le fichier ou les fiches employés."
    if status == "ok":
        return (
            f"{importable} salarié(s) prêt(s) : l'enregistrement mettra à jour "
            "le calendrier prévu (heures planifiées, absences, CP)."
        )
    if errors:
        return (
            f"{importable} salarié(s) prêts. Associez les {errors} feuille(s) ci-dessous "
            "ou enregistrez pour n'importer que les salariés déjà reconnus."
        )
    return (
        f"{importable} salarié(s) importables — vérifiez les rapprochements approximatifs "
        "ci-dessous avant d'enregistrer."
    )


__all__ = ["build_planning_import_summary"]
