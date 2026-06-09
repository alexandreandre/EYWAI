"""
Mappers expenses (dict Supabase <-> entités / préparation données).

Logique de préparation des données pour la DB et de conversion row <-> entity.
Comportement identique à l'ancien router (format date, clés, statut initial).
"""

from datetime import date, datetime
from typing import Any, Dict

from app.modules.expenses.domain.entities import ExpenseReportEntity
from app.modules.expenses.domain.rules import get_initial_expense_status
from app.modules.expenses.domain.vat import compute_vat_breakdown


def build_create_payload(
    employee_id: str,
    date_value: date,
    amount: float,
    vat_rate: float,
    type_value: str,
    description: str | None = None,
    receipt_url: str | None = None,
    filename: str | None = None,
    company_id: str | None = None,
) -> Dict[str, Any]:
    """
    Construit le dictionnaire pour l'insert Supabase (table expense_reports).
    Comportement identique à create_expense_report du router legacy :
    - date en isoformat, status depuis la règle domaine, filename présent.
    """
    amount_ht, vat_amount = compute_vat_breakdown(amount, vat_rate)
    payload = {
        "employee_id": employee_id,
        "date": date_value.isoformat() if isinstance(date_value, date) else date_value,
        "amount": amount,
        "vat_rate": vat_rate,
        "amount_ht": amount_ht,
        "vat_amount": vat_amount,
        "type": type_value,
        "description": description,
        "receipt_url": receipt_url,
        "filename": filename if filename is not None else None,
        "status": get_initial_expense_status(),
    }
    if company_id:
        payload["company_id"] = company_id
    if "filename" not in payload:
        payload["filename"] = None
    return payload


def row_to_entity(row: Dict[str, Any]) -> ExpenseReportEntity:
    """Mappe une ligne expense_reports (Supabase) vers ExpenseReportEntity."""
    date_val = row.get("date")
    if isinstance(date_val, str) and date_val:
        date_val = datetime.fromisoformat(date_val.replace("Z", "+00:00")).date()
    elif not isinstance(date_val, date):
        date_val = date(1970, 1, 1)
    created_at = row.get("created_at")
    if isinstance(created_at, str):
        try:
            created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            created_at = None
    return ExpenseReportEntity(
        id=row["id"],
        employee_id=row["employee_id"],
        date=date_val or date(1970, 1, 1),
        amount=float(row.get("amount", 0)),
        type=row.get("type", ""),
        status=row.get("status", "pending"),
        vat_rate=float(row["vat_rate"]) if row.get("vat_rate") is not None else None,
        amount_ht=float(row["amount_ht"]) if row.get("amount_ht") is not None else None,
        vat_amount=float(row["vat_amount"]) if row.get("vat_amount") is not None else None,
        company_id=row.get("company_id"),
        description=row.get("description"),
        receipt_url=row.get("receipt_url"),
        filename=row.get("filename"),
        created_at=created_at,
    )


def entity_to_row(entity: ExpenseReportEntity) -> Dict[str, Any]:
    """Mappe ExpenseReportEntity vers dict pour insert/update Supabase."""
    return {
        "id": entity.id,
        "employee_id": entity.employee_id,
        "company_id": entity.company_id,
        "date": entity.date.isoformat()
        if isinstance(entity.date, date)
        else entity.date,
        "amount": entity.amount,
        "vat_rate": entity.vat_rate,
        "amount_ht": entity.amount_ht,
        "vat_amount": entity.vat_amount,
        "type": entity.type,
        "description": entity.description,
        "receipt_url": entity.receipt_url,
        "filename": entity.filename,
        "status": entity.status,
        "created_at": entity.created_at.isoformat() if entity.created_at else None,
    }
