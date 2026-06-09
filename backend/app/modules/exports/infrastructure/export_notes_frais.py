# Export « Notes de frais » — format cabinet comptable (générique, Quadra, Sage).
from __future__ import annotations

import csv
import io
from calendar import monthrange
from typing import Any, Dict, List, Literal, Optional, Tuple

from app.core.database import supabase
from app.shared.utils.export import format_period, generate_csv, generate_xlsx

CabinetFormat = Literal["generique", "quadra", "sage"]

DEFAULT_JOURNAL = "OD"
DEFAULT_TVA_ACCOUNT = "445660"
DEFAULT_EMPLOYEE_ACCOUNT = "421000"

EXPENSE_TYPE_ACCOUNTS: Dict[str, str] = {
    "Transport": "625100",
    "Restaurant": "625600",
    "Hôtel": "625600",
    "Fournitures": "625800",
    "Autre": "625000",
}

CABINET_HEADERS: Dict[CabinetFormat, List[str]] = {
    "generique": [
        "Date",
        "Journal",
        "Compte",
        "Libellé",
        "Débit",
        "Crédit",
        "Analytique",
        "Référence",
        "Période",
    ],
    "quadra": [
        "Journal",
        "Date",
        "Compte",
        "Libellé",
        "Débit",
        "Crédit",
        "Analytique",
    ],
    "sage": [
        "Date",
        "Journal",
        "Compte",
        "Libellé",
        "Débit",
        "Crédit",
        "Analytique",
        "Référence",
    ],
}


def _round2(value: float) -> float:
    return round(value, 2)


def _period_date_bounds(period: str) -> Tuple[str, str]:
    year, month = map(int, period.split("-"))
    last_day = monthrange(year, month)[1]
    return f"{year}-{month:02d}-01", f"{year}-{month:02d}-{last_day:02d}"


def _resolve_company_employee_ids(
    company_id: str,
    employee_ids: Optional[List[str]] = None,
) -> List[str]:
    query = supabase.table("employees").select("id").eq("company_id", company_id)
    if employee_ids:
        query = query.in_("id", employee_ids)
    response = query.execute()
    return [row["id"] for row in (response.data or [])]


def get_expense_reports_for_export(
    company_id: str,
    period: str,
    employee_ids: Optional[List[str]] = None,
    status: str = "validated",
    expense_types: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """Récupère les notes de frais exportables pour une entreprise et une période."""
    scoped_employee_ids = _resolve_company_employee_ids(company_id, employee_ids)
    if not scoped_employee_ids:
        return []

    start_date, end_date = _period_date_bounds(period)
    query = (
        supabase.table("expense_reports")
        .select(
            """
            id,
            employee_id,
            date,
            amount,
            vat_rate,
            amount_ht,
            vat_amount,
            type,
            description,
            status,
            filename,
            employees!inner(
                id,
                first_name,
                last_name,
                company_id,
                employee_number
            )
            """
        )
        .eq("status", status)
        .in_("employee_id", scoped_employee_ids)
        .gte("date", start_date)
        .lte("date", end_date)
    )
    if expense_types:
        query = query.in_("type", expense_types)

    response = query.order("date").execute()
    rows = response.data or []

    normalized: List[Dict[str, Any]] = []
    for row in rows:
        employee = row.get("employees") or {}
        if employee.get("company_id") and employee.get("company_id") != company_id:
            continue
        normalized.append(
            {
                "id": row.get("id"),
                "employee_id": row.get("employee_id"),
                "date": row.get("date"),
                "amount": float(row.get("amount") or 0),
                "vat_rate": float(row.get("vat_rate") or 0),
                "amount_ht": float(row.get("amount_ht") or 0),
                "vat_amount": float(row.get("vat_amount") or 0),
                "type": row.get("type") or "Autre",
                "description": row.get("description") or "",
                "status": row.get("status"),
                "filename": row.get("filename"),
                "employee_first_name": employee.get("first_name") or "",
                "employee_last_name": employee.get("last_name") or "",
                "employee_number": employee.get("employee_number") or "",
            }
        )
    return normalized


def _charge_account_for_type(expense_type: str) -> str:
    return EXPENSE_TYPE_ACCOUNTS.get(expense_type, EXPENSE_TYPE_ACCOUNTS["Autre"])


def _employee_display_name(expense: Dict[str, Any]) -> str:
    first = expense.get("employee_first_name", "").strip()
    last = expense.get("employee_last_name", "").strip()
    return f"{first} {last}".strip() or "Salarié"


def _short_reference(expense_id: str) -> str:
    return f"NDF-{str(expense_id)[:8]}"


def build_ecritures_from_expenses(
    expenses: List[Dict[str, Any]],
    period: str,
) -> Tuple[List[Dict[str, Any]], Dict[str, float]]:
    """Construit les écritures comptables à partir des notes de frais."""
    ecritures: List[Dict[str, Any]] = []
    totals = {
        "total_ht": 0.0,
        "total_tva": 0.0,
        "total_ttc": 0.0,
        "total_debit": 0.0,
        "total_credit": 0.0,
    }

    for expense in expenses:
        amount_ttc = _round2(float(expense.get("amount") or 0))
        amount_ht = _round2(float(expense.get("amount_ht") or 0))
        vat_amount = _round2(float(expense.get("vat_amount") or 0))
        if amount_ht <= 0 and amount_ttc > 0:
            amount_ht = _round2(amount_ttc - vat_amount)
        if amount_ht <= 0 and amount_ttc <= 0:
            continue

        expense_type = expense.get("type") or "Autre"
        employee_name = _employee_display_name(expense)
        date_ecriture = expense.get("date") or period + "-01"
        reference = _short_reference(str(expense.get("id") or ""))
        libelle_base = f"NDF {expense_type} — {employee_name}"

        charge_account = _charge_account_for_type(expense_type)

        ecritures.append(
            {
                "date_ecriture": date_ecriture,
                "journal": DEFAULT_JOURNAL,
                "compte_comptable": charge_account,
                "libelle": libelle_base,
                "debit": amount_ht,
                "credit": 0.0,
                "analytique": "",
                "reference_export": reference,
                "periode_paie": period,
            }
        )
        totals["total_debit"] += amount_ht
        totals["total_ht"] += amount_ht

        if vat_amount > 0:
            ecritures.append(
                {
                    "date_ecriture": date_ecriture,
                    "journal": DEFAULT_JOURNAL,
                    "compte_comptable": DEFAULT_TVA_ACCOUNT,
                    "libelle": f"TVA {libelle_base}",
                    "debit": vat_amount,
                    "credit": 0.0,
                    "analytique": "",
                    "reference_export": reference,
                    "periode_paie": period,
                }
            )
            totals["total_debit"] += vat_amount
            totals["total_tva"] += vat_amount

        credit_amount = amount_ttc if amount_ttc > 0 else _round2(amount_ht + vat_amount)
        ecritures.append(
            {
                "date_ecriture": date_ecriture,
                "journal": DEFAULT_JOURNAL,
                "compte_comptable": DEFAULT_EMPLOYEE_ACCOUNT,
                "libelle": f"Dette NDF {employee_name}",
                "debit": 0.0,
                "credit": credit_amount,
                "analytique": "",
                "reference_export": reference,
                "periode_paie": period,
            }
        )
        totals["total_credit"] += credit_amount
        totals["total_ttc"] += credit_amount

    totals["total_ht"] = _round2(totals["total_ht"])
    totals["total_tva"] = _round2(totals["total_tva"])
    totals["total_ttc"] = _round2(totals["total_ttc"])
    totals["total_debit"] = _round2(totals["total_debit"])
    totals["total_credit"] = _round2(totals["total_credit"])
    totals["equilibre"] = totals["total_debit"] == totals["total_credit"]
    totals["ecart"] = _round2(abs(totals["total_debit"] - totals["total_credit"]))

    return ecritures, totals


def _format_cabinet_rows(
    ecritures: List[Dict[str, Any]],
    cabinet_format: CabinetFormat,
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for entry in ecritures:
        date_value = entry["date_ecriture"]
        if cabinet_format == "quadra":
            date_value = str(date_value).replace("-", "/")
        if cabinet_format == "generique":
            rows.append(
                {
                    "Date": date_value,
                    "Journal": entry["journal"],
                    "Compte": entry["compte_comptable"],
                    "Libellé": entry["libelle"],
                    "Débit": entry["debit"],
                    "Crédit": entry["credit"],
                    "Analytique": entry.get("analytique", ""),
                    "Référence": entry.get("reference_export", ""),
                    "Période": entry["periode_paie"],
                }
            )
        elif cabinet_format == "quadra":
            rows.append(
                {
                    "Journal": entry["journal"],
                    "Date": date_value,
                    "Compte": entry["compte_comptable"],
                    "Libellé": entry["libelle"],
                    "Débit": entry["debit"],
                    "Crédit": entry["credit"],
                    "Analytique": entry.get("analytique", ""),
                }
            )
        else:
            rows.append(
                {
                    "Date": date_value,
                    "Journal": entry["journal"],
                    "Compte": entry["compte_comptable"],
                    "Libellé": entry["libelle"],
                    "Débit": entry["debit"],
                    "Crédit": entry["credit"],
                    "Analytique": entry.get("analytique", ""),
                    "Référence": entry.get("reference_export", ""),
                }
            )
    return rows


def _generate_cabinet_file(
    ecritures: List[Dict[str, Any]],
    period: str,
    cabinet_format: CabinetFormat,
    file_format: str,
) -> bytes:
    headers = CABINET_HEADERS[cabinet_format]
    data = _format_cabinet_rows(ecritures, cabinet_format)
    labels = {
        "generique": "Export Cabinet NDF",
        "quadra": "Quadra NDF",
        "sage": "Sage NDF",
    }
    sheet_name = f"{labels[cabinet_format]} {format_period(period)}"

    if file_format == "xlsx":
        return generate_xlsx(data, headers, sheet_name)

    if cabinet_format == "quadra":
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=headers, delimiter=";")
        writer.writeheader()
        for row in data:
            writer.writerow(row)
        return output.getvalue().encode("utf-8")

    return generate_csv(data, headers)


def preview_notes_frais(
    company_id: str,
    period: str,
    employee_ids: Optional[List[str]] = None,
    expense_types: Optional[List[str]] = None,
) -> Dict[str, Any]:
    expenses = get_expense_reports_for_export(
        company_id,
        period,
        employee_ids,
        status="validated",
        expense_types=expense_types,
    )
    ecritures, totals = build_ecritures_from_expenses(expenses, period)

    anomalies: List[Dict[str, Any]] = []
    warnings: List[str] = []

    if not expenses:
        anomalies.append(
            {
                "type": "error",
                "message": "Aucune note de frais validée trouvée pour cette période",
                "severity": "blocking",
            }
        )

    if expenses and not totals.get("equilibre", True):
        anomalies.append(
            {
                "type": "error",
                "message": "Les écritures comptables ne sont pas équilibrées",
                "severity": "blocking",
            }
        )

    warnings.append(
        "Utilisation des comptes comptables par défaut. "
        "Configurez vos mappings comptables pour personnaliser."
    )

    employee_ids_found = {exp["employee_id"] for exp in expenses if exp.get("employee_id")}

    return {
        "employees_count": len(employee_ids_found),
        "totals": {
            "employees_count": len(employee_ids_found),
            "expenses_count": len(expenses),
            "total_ht": totals["total_ht"],
            "total_tva": totals["total_tva"],
            "total_ttc": totals["total_ttc"],
            "total_amount": totals["total_ttc"],
            "total_debit": totals["total_debit"],
            "total_credit": totals["total_credit"],
            "equilibre": totals["equilibre"],
            "ecart": totals["ecart"],
        },
        "anomalies": anomalies,
        "warnings": warnings,
        "can_generate": len([a for a in anomalies if a.get("severity") == "blocking"]) == 0,
        "details": {
            "lines_count": len(ecritures),
            "expenses_count": len(expenses),
        },
    }


def generate_notes_frais_export(
    company_id: str,
    period: str,
    employee_ids: Optional[List[str]] = None,
    file_format: str = "xlsx",
    cabinet_format: CabinetFormat = "generique",
    expense_types: Optional[List[str]] = None,
) -> bytes:
    expenses = get_expense_reports_for_export(
        company_id,
        period,
        employee_ids,
        status="validated",
        expense_types=expense_types,
    )
    ecritures, _ = build_ecritures_from_expenses(expenses, period)
    return _generate_cabinet_file(ecritures, period, cabinet_format, file_format)
