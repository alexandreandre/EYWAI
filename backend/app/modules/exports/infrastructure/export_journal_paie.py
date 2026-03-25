# Implémentation locale du générateur Journal de paie (ex-services.exports.journal_paie).
from typing import Any, Dict, List, Optional

from app.core.database import supabase
from app.shared.utils.export import format_period, generate_csv, generate_xlsx


def get_journal_paie_data(
    company_id: str,
    period: str,
    employee_ids: Optional[List[str]] = None,
) -> tuple:
    """Récupère les données du journal de paie pour une période donnée. Retourne (données, totaux)."""
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
            contract_type,
            statut,
            company_id
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

    journal_data = []
    totals = {
        "employees_count": 0,
        "total_brut": 0.0,
        "total_cotisations_salariales": 0.0,
        "total_cotisations_patronales": 0.0,
        "total_net_imposable": 0.0,
        "total_net_a_payer": 0.0,
    }

    for payslip in payslips:
        employee = payslip.get("employees", {})
        payslip_data = payslip.get("payslip_data", {})

        if not isinstance(payslip_data, dict):
            continue

        brut = float(payslip_data.get("salaire_brut", 0) or 0)
        net_a_payer = float(payslip_data.get("net_a_payer", 0) or 0)

        synthese_net = payslip_data.get("synthese_net", {})
        net_imposable = float(
            synthese_net.get("net_imposable", 0)
            if isinstance(synthese_net, dict)
            else 0
        )

        cotisations = payslip_data.get("structure_cotisations", {})
        cotisations_list = (
            cotisations.get("cotisations", []) if isinstance(cotisations, dict) else []
        )

        cotisations_salariales = 0.0
        cotisations_patronales = 0.0

        for coti in cotisations_list:
            if isinstance(coti, dict):
                cotisations_salariales += float(coti.get("montant_salarial", 0) or 0)
                cotisations_patronales += float(coti.get("montant_patronal", 0) or 0)

        pas = 0.0
        if isinstance(synthese_net, dict):
            pas = float(synthese_net.get("impot_preleve_a_la_source", 0) or 0)

        row = {
            "Matricule": employee.get("id", "")[:8],
            "Nom": employee.get("last_name", ""),
            "Prénom": employee.get("first_name", ""),
            "Type de contrat": employee.get("contract_type", ""),
            "Statut": employee.get("statut", ""),
            "Établissement": "",
            "Période": format_period(period),
            "Brut": brut,
            "Charges salariales": cotisations_salariales,
            "Charges patronales": cotisations_patronales,
            "Net imposable": net_imposable,
            "PAS": pas,
            "Net à payer": net_a_payer,
            "Devise": "EUR",
        }
        journal_data.append(row)

        totals["employees_count"] += 1
        totals["total_brut"] += brut
        totals["total_cotisations_salariales"] += cotisations_salariales
        totals["total_cotisations_patronales"] += cotisations_patronales
        totals["total_net_imposable"] += net_imposable
        totals["total_net_a_payer"] += net_a_payer

    return journal_data, totals


def generate_journal_paie_export(
    company_id: str,
    period: str,
    employee_ids: Optional[List[str]] = None,
    format: str = "csv",
) -> bytes:
    data, totals = get_journal_paie_data(company_id, period, employee_ids)

    headers = [
        "Matricule",
        "Nom",
        "Prénom",
        "Type de contrat",
        "Statut",
        "Établissement",
        "Période",
        "Brut",
        "Charges salariales",
        "Charges patronales",
        "Net imposable",
        "PAS",
        "Net à payer",
        "Devise",
    ]

    if format == "xlsx":
        return generate_xlsx(data, headers, f"Journal de paie {format_period(period)}")
    return generate_csv(data, headers)


def preview_journal_paie(
    company_id: str,
    period: str,
    employee_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    data, totals = get_journal_paie_data(company_id, period, employee_ids)

    anomalies = []
    warnings = []

    if totals["employees_count"] == 0:
        warnings.append("Aucun bulletin trouvé pour cette période")

    if totals["employees_count"] > 0:
        expected_net = (
            totals["total_brut"]
            - totals["total_cotisations_salariales"]
            - totals.get("total_pas", 0)
        )
        diff = abs(totals["total_net_a_payer"] - expected_net)
        if diff > 1.0:
            warnings.append(
                f"Écart de {diff:.2f}€ entre le net calculé et le net à payer"
            )

    return {
        "employees_count": totals["employees_count"],
        "totals": totals,
        "anomalies": anomalies,
        "warnings": warnings,
        "can_generate": len([a for a in anomalies if a.get("severity") == "blocking"])
        == 0,
    }
