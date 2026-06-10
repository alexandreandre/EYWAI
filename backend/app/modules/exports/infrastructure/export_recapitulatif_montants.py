# Export « Récapitulatif des montants » — synthèse des nets à payer par salarié.
from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.modules.exports.infrastructure.export_paiement_salaires import (
    get_paiement_salaires_data,
)
from app.shared.utils.export import format_period, generate_csv, generate_xlsx

RECAP_HEADERS = [
    "Matricule",
    "Nom",
    "Prénom",
    "Montant net à payer",
    "Devise",
    "Statut contrôle",
]


def preview_recapitulatif_montants(
    company_id: str,
    period: str,
    employee_ids: Optional[List[str]] = None,
    excluded_employee_ids: Optional[List[str]] = None,
    execution_date: Optional[str] = None,
    payment_label: Optional[str] = None,
) -> Dict[str, Any]:
    data, totals, anomalies, warnings = get_paiement_salaires_data(
        company_id,
        period,
        employee_ids,
        excluded_employee_ids,
        execution_date,
        payment_label,
    )

    if totals["virements_count"] == 0:
        warnings.append("Aucun montant à récapituler pour cette période")

    blocking = [a for a in anomalies if a.get("severity") == "blocking"]
    return {
        "employees_count": totals["virements_count"],
        "totals": {
            "employees_count": totals["virements_count"],
            "total_net_a_payer": totals.get("total_amount", 0.0),
            "total_amount": totals.get("total_amount", 0.0),
        },
        "anomalies": anomalies,
        "warnings": warnings,
        "can_generate": len(blocking) == 0 and totals["virements_count"] > 0,
        "details": {
            "lines_count": len(data),
            "blocking_count": len(blocking),
        },
    }


def generate_recapitulatif_montants_export(
    company_id: str,
    period: str,
    employee_ids: Optional[List[str]] = None,
    excluded_employee_ids: Optional[List[str]] = None,
    execution_date: Optional[str] = None,
    payment_label: Optional[str] = None,
    file_format: str = "csv",
) -> bytes:
    data, _, anomalies, _ = get_paiement_salaires_data(
        company_id,
        period,
        employee_ids,
        excluded_employee_ids,
        execution_date,
        payment_label,
    )
    valid_data = [row for row in data if row.get("Statut_controle") != "Bloquant"]
    recap_rows = [
        {
            "Matricule": row.get("Matricule", ""),
            "Nom": row.get("Nom", ""),
            "Prénom": row.get("Prénom", ""),
            "Montant net à payer": row.get("Montant", 0),
            "Devise": row.get("Devise", "EUR"),
            "Statut contrôle": row.get("Statut_controle", ""),
        }
        for row in valid_data
    ]
    sheet_name = f"Récap montants {format_period(period)}"
    if file_format == "xlsx":
        return generate_xlsx(recap_rows, RECAP_HEADERS, sheet_name)
    return generate_csv(recap_rows, RECAP_HEADERS)
