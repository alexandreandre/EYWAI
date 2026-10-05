# Implémentation locale du générateur Journal de paie (ex-services.exports.journal_paie).
from typing import Any, Dict, List, Optional

from app.core.database import supabase
from app.modules.exports.domain.controle_comptable import (
    conseil_bulletin_incoherent,
    residu_du_bulletin,
)
from app.modules.exports.infrastructure.export_ecritures_comptables import (
    ligne_od_du_bulletin,
)
from app.modules.exports.infrastructure.payslip_accounting_extract import (
    extract_cotisations_from_payslip,
    extract_pas_amount,
)
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
            company_id,
            companies(company_name)
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
        "total_pas": 0.0,
        # Bulletins dont le net ne se reconstruit pas au centime (brut −
        # cotisations − PAS + éléments hors brut − retenues).
        "bulletins_incoherents": [],
    }

    for payslip in payslips:
        employee = payslip.get("employees", {})
        payslip_data = payslip.get("payslip_data", {})

        if not isinstance(payslip_data, dict):
            continue

        company_info = employee.get("companies") or {}
        if isinstance(company_info, list) and company_info:
            company_info = company_info[0]
        establishment_label = (
            company_info.get("company_name")
            or company_info.get("name")
            or ""
        )

        brut = float(payslip_data.get("salaire_brut", 0) or 0)
        net_a_payer = float(payslip_data.get("net_a_payer", 0) or 0)

        synthese_net = payslip_data.get("synthese_net", {})
        net_imposable = float(
            synthese_net.get("net_imposable", 0)
            if isinstance(synthese_net, dict)
            else 0
        )

        pas = extract_pas_amount(synthese_net)
        cotisations_salariales, cotisations_patronales, _, _ = extract_cotisations_from_payslip(
            payslip_data
        )

        row = {
            "Matricule": employee.get("id", "")[:8],
            "Nom": employee.get("last_name", ""),
            "Prénom": employee.get("first_name", ""),
            "Type de contrat": employee.get("contract_type", ""),
            "Statut": employee.get("statut", ""),
            "Établissement": establishment_label,
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
        totals["total_pas"] += pas

        residu = residu_du_bulletin(
            ligne_od_du_bulletin(
                payslip_id=payslip.get("id"),
                employee=employee,
                payslip_data=payslip_data,
                saisies_du_salarie=[],
                compte_de_saisie=lambda _type: "",
            )
        )
        if residu:
            totals["bulletins_incoherents"].append(
                {
                    "employee_name": f"{employee.get('first_name', '')} {employee.get('last_name', '')}".strip(),
                    "residu": residu,
                    "reprise": bool(payslip_data.get("reprise")),
                }
            )

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
        anomalies.append(
            {
                "type": "error",
                "message": "Aucun bulletin de paie validé pour cette période",
                "severity": "blocking",
            }
        )

    for bulletin in totals.get("bulletins_incoherents") or []:
        ecart = f"{abs(bulletin['residu']):.2f}".replace(".", ",")
        warnings.append(
            f"{bulletin['employee_name']} : le net à payer ne se retrouve pas à partir "
            f"du bulletin (écart de {ecart} €) — "
            f"{conseil_bulletin_incoherent(bool(bulletin.get('reprise')))}"
        )

    return {
        "employees_count": totals["employees_count"],
        "totals": totals,
        "anomalies": anomalies,
        "warnings": warnings,
        "can_generate": len([a for a in anomalies if a.get("severity") == "blocking"])
        == 0
        and totals["employees_count"] > 0,
    }
