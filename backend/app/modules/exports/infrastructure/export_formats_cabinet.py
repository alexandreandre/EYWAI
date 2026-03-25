# Implémentation locale des formats cabinet (ex-services.exports.formats_cabinet).
import csv
import io
from typing import Any, Dict, List, Optional

from app.shared.utils.export import format_period, generate_csv, generate_xlsx

from .export_ecritures_comptables import (
    generate_od_charges_sociales,
    generate_od_pas,
    generate_od_salaires,
    get_payslip_data_for_od,
)


def generate_cabinet_generic_export(
    company_id: str,
    period: str,
    employee_ids: Optional[List[str]] = None,
    format: str = "csv",
) -> bytes:
    ecritures_salaires, _, _ = generate_od_salaires(company_id, period, employee_ids)
    ecritures_charges, _, _ = generate_od_charges_sociales(
        company_id, period, employee_ids
    )
    ecritures_pas, _, _ = generate_od_pas(company_id, period, employee_ids)
    all_ecritures = ecritures_salaires + ecritures_charges + ecritures_pas

    headers = [
        "Date",
        "Journal",
        "Compte",
        "Libellé",
        "Débit",
        "Crédit",
        "Analytique",
        "Référence",
        "Période",
    ]
    data = [
        {
            "Date": e["date_ecriture"],
            "Journal": e["journal"],
            "Compte": e["compte_comptable"],
            "Libellé": e["libelle"],
            "Débit": e["debit"],
            "Crédit": e["credit"],
            "Analytique": e.get("analytique", ""),
            "Référence": e.get("reference_export", ""),
            "Période": e["periode_paie"],
        }
        for e in all_ecritures
    ]
    sheet_name = f"Export Cabinet {format_period(period)}"
    if format == "xlsx":
        return generate_xlsx(data, headers, sheet_name)
    return generate_csv(data, headers)


def generate_cabinet_quadra_export(
    company_id: str,
    period: str,
    employee_ids: Optional[List[str]] = None,
    format: str = "csv",
) -> bytes:
    ecritures_salaires, _, _ = generate_od_salaires(company_id, period, employee_ids)
    ecritures_charges, _, _ = generate_od_charges_sociales(
        company_id, period, employee_ids
    )
    ecritures_pas, _, _ = generate_od_pas(company_id, period, employee_ids)
    all_ecritures = ecritures_salaires + ecritures_charges + ecritures_pas

    headers = [
        "Journal",
        "Date",
        "Compte",
        "Libellé",
        "Débit",
        "Crédit",
        "Analytique",
    ]
    data = [
        {
            "Journal": e["journal"],
            "Date": e["date_ecriture"].replace("-", "/"),
            "Compte": e["compte_comptable"],
            "Libellé": e["libelle"],
            "Débit": e["debit"],
            "Crédit": e["credit"],
            "Analytique": e.get("analytique", ""),
        }
        for e in all_ecritures
    ]
    sheet_name = f"Quadra {format_period(period)}"
    if format == "xlsx":
        return generate_xlsx(data, headers, sheet_name)
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=headers, delimiter=";")
    writer.writeheader()
    for row in data:
        writer.writerow(row)
    return output.getvalue().encode("utf-8")


def generate_cabinet_sage_export(
    company_id: str,
    period: str,
    employee_ids: Optional[List[str]] = None,
    format: str = "csv",
) -> bytes:
    ecritures_salaires, _, _ = generate_od_salaires(company_id, period, employee_ids)
    ecritures_charges, _, _ = generate_od_charges_sociales(
        company_id, period, employee_ids
    )
    ecritures_pas, _, _ = generate_od_pas(company_id, period, employee_ids)
    all_ecritures = ecritures_salaires + ecritures_charges + ecritures_pas

    headers = [
        "Date",
        "Journal",
        "Compte",
        "Libellé",
        "Débit",
        "Crédit",
        "Analytique",
        "Référence",
    ]
    data = [
        {
            "Date": e["date_ecriture"],
            "Journal": e["journal"],
            "Compte": e["compte_comptable"],
            "Libellé": e["libelle"],
            "Débit": e["debit"],
            "Crédit": e["credit"],
            "Analytique": e.get("analytique", ""),
            "Référence": e.get("reference_export", ""),
        }
        for e in all_ecritures
    ]
    sheet_name = f"Sage {format_period(period)}"
    if format == "xlsx":
        return generate_xlsx(data, headers, sheet_name)
    return generate_csv(data, headers)


def preview_cabinet_export(
    company_id: str,
    period: str,
    export_type: str,
    employee_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    anomalies = []
    warnings = []
    payslip_list, totals = get_payslip_data_for_od(company_id, period, employee_ids)
    if totals["employees_count"] == 0:
        anomalies.append(
            {
                "type": "error",
                "message": "Aucun bulletin trouvé pour cette période",
                "severity": "blocking",
            }
        )
    return {
        "employees_count": totals["employees_count"],
        "totals": totals,
        "anomalies": anomalies,
        "warnings": warnings,
        "can_generate": len([a for a in anomalies if a.get("severity") == "blocking"])
        == 0,
    }
