# Implémentation locale du générateur Paiement salaires (ex-services.exports.paiement_salaires).
import json
import re
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

from app.core.database import supabase
from app.shared.utils.export import format_period, generate_csv, generate_xlsx


def validate_iban(iban: str) -> bool:
    if not iban:
        return False
    iban_clean = iban.replace(" ", "").replace("-", "").upper()
    if len(iban_clean) < 15 or len(iban_clean) > 34:
        return False
    if not re.match(r"^[A-Z]{2}[0-9]{2}[A-Z0-9]+$", iban_clean):
        return False
    return True


def mask_iban(iban: str) -> str:
    if not iban:
        return ""
    iban_clean = iban.replace(" ", "").replace("-", "").upper()
    if len(iban_clean) < 8:
        return iban_clean
    return f"{iban_clean[:4]} **** **** {iban_clean[-4:]}"


def get_paiement_salaires_data(
    company_id: str,
    period: str,
    employee_ids: Optional[List[str]] = None,
    excluded_employee_ids: Optional[List[str]] = None,
    execution_date: Optional[str] = None,
    payment_label: Optional[str] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any], List[Dict[str, Any]], List[str]]:
    year, month = map(int, period.split("-"))

    query = (
        supabase.table("payslips")
        .select(
            """
        id,
        employee_id,
        month,
        year,
        payslip_data,
        employees!inner(
            id,
            first_name,
            last_name,
            coordonnees_bancaires,
            hire_date,
            contract_type,
            statut
        )
        """
        )
        .eq("company_id", company_id)
        .eq("year", year)
        .eq("month", month)
    )

    if employee_ids:
        query = query.in_("employee_id", employee_ids)

    response = query.execute()
    payslips = response.data or []

    exits_response = (
        supabase.table("employee_exits")
        .select("employee_id, exit_type, last_working_day, status")
        .eq("company_id", company_id)
        .execute()
    )
    exits = {e["employee_id"]: e for e in (exits_response.data or [])}

    paiement_data = []
    anomalies = []
    warnings = []
    totals = {"virements_count": 0, "total_amount": 0.0, "currency": "EUR"}
    seen_employees = set()

    for payslip in payslips:
        employee = payslip.get("employees", {})
        employee_id = employee.get("id")

        if employee_id in seen_employees:
            anomalies.append(
                {
                    "type": "error",
                    "message": f"Doublon détecté - {employee.get('first_name', '')} {employee.get('last_name', '')}",
                    "severity": "blocking",
                    "employee_id": employee_id,
                    "employee_name": f"{employee.get('first_name', '')} {employee.get('last_name', '')}",
                }
            )
            continue

        seen_employees.add(employee_id)

        if excluded_employee_ids and employee_id in excluded_employee_ids:
            continue

        payslip_data = payslip.get("payslip_data", {})
        if not isinstance(payslip_data, dict):
            anomalies.append(
                {
                    "type": "error",
                    "message": f"Bulletin invalide - {employee.get('first_name', '')} {employee.get('last_name', '')}",
                    "severity": "blocking",
                    "employee_id": employee_id,
                    "employee_name": f"{employee.get('first_name', '')} {employee.get('last_name', '')}",
                }
            )
            continue

        net_a_payer = float(payslip_data.get("net_a_payer", 0) or 0)

        if net_a_payer <= 0:
            anomalies.append(
                {
                    "type": "error",
                    "message": f"Montant ≤ 0 - {employee.get('first_name', '')} {employee.get('last_name', '')}",
                    "severity": "blocking",
                    "employee_id": employee_id,
                    "employee_name": f"{employee.get('first_name', '')} {employee.get('last_name', '')}",
                }
            )
            continue

        coordonnees = employee.get("coordonnees_bancaires", {})
        if isinstance(coordonnees, str):
            try:
                coordonnees = json.loads(coordonnees)
            except Exception:
                coordonnees = {}

        iban = coordonnees.get("iban", "") if isinstance(coordonnees, dict) else ""
        bic = coordonnees.get("bic", "") if isinstance(coordonnees, dict) else ""

        if not iban or not validate_iban(iban):
            anomalies.append(
                {
                    "type": "error",
                    "message": f"IBAN manquant ou invalide - {employee.get('first_name', '')} {employee.get('last_name', '')}",
                    "severity": "blocking",
                    "employee_id": employee_id,
                    "employee_name": f"{employee.get('first_name', '')} {employee.get('last_name', '')}",
                }
            )
            continue

        iban_clean = iban.replace(" ", "").replace("-", "").upper()
        control_status = "OK"
        employee_warnings = []

        if employee_id in exits:
            exit_info = exits[employee_id]
            last_working_day = exit_info.get("last_working_day")
            if last_working_day:
                try:
                    exit_date = (
                        datetime.strptime(last_working_day, "%Y-%m-%d").date()
                        if isinstance(last_working_day, str)
                        else last_working_day
                    )
                    period_date = date(year, month, 1)
                    if exit_date < period_date:
                        employee_warnings.append("Salarié sorti mais payé")
                        control_status = "Alerte"
                except Exception:
                    pass

        brut = float(payslip_data.get("salaire_brut", 0) or 0)
        if brut > 0:
            ratio = net_a_payer / brut
            if ratio > 0.9:
                employee_warnings.append(
                    "Net exceptionnellement élevé par rapport au brut"
                )
                if control_status == "OK":
                    control_status = "Alerte"
            elif ratio < 0.4:
                employee_warnings.append(
                    "Net exceptionnellement faible par rapport au brut"
                )
                if control_status == "OK":
                    control_status = "Alerte"

        for w in employee_warnings:
            warnings.append(
                f"{employee.get('first_name', '')} {employee.get('last_name', '')}: {w}"
            )

        row = {
            "Matricule": employee_id[:8],
            "Nom": employee.get("last_name", ""),
            "Prénom": employee.get("first_name", ""),
            "IBAN": iban_clean,
            "IBAN_Masque": mask_iban(iban),
            "BIC": bic.upper() if bic else "",
            "Montant": net_a_payer,
            "Devise": "EUR",
            "Statut_controle": control_status,
        }
        paiement_data.append(row)
        totals["virements_count"] += 1
        totals["total_amount"] += net_a_payer

    return paiement_data, totals, anomalies, warnings


def preview_paiement_salaires(
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
        warnings.append("Aucun virement à générer pour cette période")
    return {
        "employees_count": totals["virements_count"],
        "totals": totals,
        "anomalies": anomalies,
        "warnings": warnings,
        "can_generate": len([a for a in anomalies if a.get("severity") == "blocking"])
        == 0
        and totals["virements_count"] > 0,
    }


def generate_paiement_salaires_export(
    company_id: str,
    period: str,
    employee_ids: Optional[List[str]] = None,
    excluded_employee_ids: Optional[List[str]] = None,
    execution_date: Optional[str] = None,
    payment_label: Optional[str] = None,
    format: str = "csv",
) -> bytes:
    data, totals, anomalies, warnings = get_paiement_salaires_data(
        company_id,
        period,
        employee_ids,
        excluded_employee_ids,
        execution_date,
        payment_label,
    )
    valid_data = [row for row in data if row.get("Statut_controle") != "Bloquant"]

    headers = [
        "Matricule",
        "Nom",
        "Prénom",
        "IBAN",
        "BIC",
        "Montant",
        "Devise",
        "Statut_controle",
    ]
    if format == "xlsx":
        return generate_xlsx(
            valid_data, headers, f"Virement salaires {format_period(period)}"
        )
    return generate_csv(valid_data, headers)


def generate_bank_file(
    company_id: str,
    period: str,
    employee_ids: Optional[List[str]] = None,
    excluded_employee_ids: Optional[List[str]] = None,
    execution_date: Optional[str] = None,
    payment_label: Optional[str] = None,
) -> bytes:
    data, totals, anomalies, warnings = get_paiement_salaires_data(
        company_id,
        period,
        employee_ids,
        excluded_employee_ids,
        execution_date,
        payment_label,
    )
    valid_data = [row for row in data if row.get("Statut_controle") != "Bloquant"]
    bank_headers = [
        "IBAN",
        "BIC",
        "Nom",
        "Prénom",
        "Montant",
        "Devise",
        "Libelle",
    ]
    bank_data = [
        {
            "IBAN": row["IBAN"],
            "BIC": row["BIC"],
            "Nom": row["Nom"],
            "Prénom": row["Prénom"],
            "Montant": row["Montant"],
            "Devise": row["Devise"],
            "Libelle": payment_label or f"Salaire {format_period(period)}",
        }
        for row in valid_data
    ]
    return generate_csv(bank_data, bank_headers)
