# Export « Congés payés / Absences » — liste des absences validées sur une période.
from __future__ import annotations

from calendar import monthrange
from typing import Any, Dict, List, Optional, Tuple

from app.core.database import supabase
from app.shared.utils.export import format_period, generate_csv, generate_xlsx

ABSENCE_TYPE_LABELS: Dict[str, str] = {
    "conge_paye": "Congé payé",
    "rtt": "RTT",
    "maladie": "Maladie",
    "sans_solde": "Sans solde",
}

EXPORT_HEADERS = [
    "Nom",
    "Prénom",
    "Type",
    "Statut",
    "Nombre de jours",
    "Période",
]


def _period_date_bounds(period: str) -> Tuple[str, str]:
    year, month = map(int, period.split("-"))
    last_day = monthrange(year, month)[1]
    return f"{year}-{month:02d}-01", f"{year}-{month:02d}-{last_day:02d}"


def _days_in_period(selected_days: List[Any], period: str) -> List[str]:
    start_date, end_date = _period_date_bounds(period)
    matched: List[str] = []
    for day in selected_days or []:
        day_str = str(day)[:10]
        if start_date <= day_str <= end_date:
            matched.append(day_str)
    return sorted(set(matched))


def get_absences_for_export(
    company_id: str,
    period: str,
    employee_ids: Optional[List[str]] = None,
    absence_types: Optional[List[str]] = None,
    status: str = "validated",
) -> List[Dict[str, Any]]:
    query = (
        supabase.table("absence_requests")
        .select(
            """
            id,
            employee_id,
            type,
            status,
            selected_days,
            comment,
            employee:employees(id, first_name, last_name)
            """
        )
        .eq("company_id", company_id)
        .eq("status", status)
    )
    if employee_ids:
        query = query.in_("employee_id", employee_ids)
    if absence_types:
        query = query.in_("type", absence_types)

    response = query.order("created_at").execute()
    rows = response.data or []

    normalized: List[Dict[str, Any]] = []
    for row in rows:
        days_in_period = _days_in_period(row.get("selected_days") or [], period)
        if not days_in_period:
            continue
        employee = row.get("employee") or {}
        absence_type = row.get("type") or ""
        normalized.append(
            {
                "id": row.get("id"),
                "employee_id": row.get("employee_id"),
                "type": absence_type,
                "type_label": ABSENCE_TYPE_LABELS.get(absence_type, absence_type),
                "status": row.get("status"),
                "days_count": len(days_in_period),
                "days_in_period": days_in_period,
                "employee_first_name": employee.get("first_name") or "",
                "employee_last_name": employee.get("last_name") or "",
            }
        )
    return normalized


def _build_export_rows(
    absences: List[Dict[str, Any]],
    period: str,
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for absence in absences:
        rows.append(
            {
                "Nom": absence.get("employee_last_name", ""),
                "Prénom": absence.get("employee_first_name", ""),
                "Type": absence.get("type_label", ""),
                "Statut": absence.get("status", ""),
                "Nombre de jours": absence.get("days_count", 0),
                "Période": format_period(period),
            }
        )
    return rows


def preview_conges_absences(
    company_id: str,
    period: str,
    employee_ids: Optional[List[str]] = None,
    absence_types: Optional[List[str]] = None,
) -> Dict[str, Any]:
    absences = get_absences_for_export(
        company_id,
        period,
        employee_ids,
        absence_types,
        status="validated",
    )
    total_days = sum(a.get("days_count", 0) for a in absences)
    employee_ids_found = {a["employee_id"] for a in absences if a.get("employee_id")}

    anomalies: List[Dict[str, Any]] = []
    warnings: List[str] = []

    if not absences:
        anomalies.append(
            {
                "type": "error",
                "message": "Aucune absence validée trouvée pour cette période",
                "severity": "blocking",
            }
        )

    return {
        "employees_count": len(employee_ids_found),
        "totals": {
            "employees_count": len(employee_ids_found),
            "absences_count": len(absences),
            "total_days": total_days,
            "total_amount": float(total_days),
        },
        "anomalies": anomalies,
        "warnings": warnings,
        "can_generate": len([a for a in anomalies if a.get("severity") == "blocking"]) == 0,
        "details": {
            "absences_count": len(absences),
            "total_days": total_days,
        },
    }


def generate_conges_absences_export(
    company_id: str,
    period: str,
    employee_ids: Optional[List[str]] = None,
    file_format: str = "xlsx",
    absence_types: Optional[List[str]] = None,
) -> bytes:
    absences = get_absences_for_export(
        company_id,
        period,
        employee_ids,
        absence_types,
        status="validated",
    )
    data = _build_export_rows(absences, period)
    sheet_name = f"Congés absences {format_period(period)}"
    if file_format == "xlsx":
        return generate_xlsx(data, EXPORT_HEADERS, sheet_name)
    return generate_csv(data, EXPORT_HEADERS)
