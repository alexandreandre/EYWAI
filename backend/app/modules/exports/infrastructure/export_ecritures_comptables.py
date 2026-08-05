from app.core.logging import get_logger

logger = get_logger("modules.exports.infrastructure.export_ecritures_comptables")
# Implémentation locale des écritures comptables OD (ex-services.exports.ecritures_comptables).
from typing import Any, Dict, List, Optional, Tuple

from app.core.database import supabase
from app.modules.exports.infrastructure.payslip_accounting_extract import (
    extract_cotisations_from_payslip,
    extract_elements_hors_brut,
    extract_pas_amount,
)
from app.shared.utils.export import format_period, generate_csv, generate_xlsx

DEFAULT_MAPPINGS = {
    "salaire_brut": {
        "rubrique_code": "salaire_brut",
        "rubrique_libelle": "Salaire brut",
        "compte_comptable": "641000",
        "sens": "debit",
        "type_rubrique": "salaire",
        "journal": "OD",
    },
    "net_a_payer": {
        "rubrique_code": "net_a_payer",
        "rubrique_libelle": "Net à payer",
        "compte_comptable": "425000",
        "sens": "credit",
        "type_rubrique": "dette_salarie",
        "journal": "OD",
    },
    "cotisation_salariale": {
        "rubrique_code": "cotisation_salariale",
        "rubrique_libelle": "Cotisations salariales",
        "compte_comptable": "425000",
        "sens": "credit",
        "type_rubrique": "dette_salarie",
        "journal": "OD",
    },
    "cotisation_patronale": {
        "rubrique_code": "cotisation_patronale",
        "rubrique_libelle": "Charges sociales patronales",
        "compte_comptable": "645000",
        "sens": "debit",
        "type_rubrique": "charge_patronale",
        "journal": "OD",
    },
    "pas": {
        "rubrique_code": "pas",
        "rubrique_libelle": "Prélèvement à la source",
        "compte_comptable": "425100",
        "sens": "credit",
        "type_rubrique": "pas",
        "journal": "OD",
    },
}


def get_accounting_mappings(company_id: str) -> Dict[str, Dict[str, Any]]:
    try:
        global_response = (
            supabase.table("accounting_mappings")
            .select("*")
            .is_("company_id", "null")
            .eq("is_active", True)
            .execute()
        )
        company_response = (
            supabase.table("accounting_mappings")
            .select("*")
            .eq("company_id", company_id)
            .eq("is_active", True)
            .execute()
        )
        by_code: Dict[str, Dict[str, Any]] = {
            m["rubrique_code"]: m for m in (global_response.data or [])
        }
        for m in company_response.data or []:
            by_code[m["rubrique_code"]] = m
        return by_code
    except Exception as e:
        logger.warning(f'Erreur lors de la récupération des mappings: {e}')
        return {}


def get_default_mapping(rubrique_code: str) -> Optional[Dict[str, Any]]:
    return DEFAULT_MAPPINGS.get(rubrique_code)


def get_payslip_data_for_od(
    company_id: str,
    period: str,
    employee_ids: Optional[List[str]] = None,
    od_type: str = "od_salaires",
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
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

    totals = {
        "total_brut": 0.0,
        "total_net_a_payer": 0.0,
        "total_cotisations_salariales": 0.0,
        "total_cotisations_patronales": 0.0,
        "total_pas": 0.0,
        "employees_count": 0,
    }
    payslip_list = []

    for payslip in payslips:
        employee = payslip.get("employees", {})
        payslip_data = payslip.get("payslip_data", {})

        if not isinstance(payslip_data, dict):
            continue

        brut = float(payslip_data.get("salaire_brut", 0) or 0)
        net_a_payer = float(payslip_data.get("net_a_payer", 0) or 0)
        synthese_net = payslip_data.get("synthese_net", {})
        pas = extract_pas_amount(synthese_net)
        cotisations_salariales, cotisations_patronales, cotisations_list, _cot_meta = (
            extract_cotisations_from_payslip(payslip_data)
        )

        company_info = employee.get("companies") or {}
        if isinstance(company_info, list) and company_info:
            company_info = company_info[0]
        establishment_label = (
            company_info.get("company_name")
            or company_info.get("name")
            or "Principal"
        )

        payslip_list.append(
            {
                "payslip_id": payslip["id"],
                "employee_id": employee.get("id"),
                "employee_name": f"{employee.get('first_name', '')} {employee.get('last_name', '')}".strip(),
                "establishment_label": establishment_label,
                "brut": brut,
                "net_a_payer": net_a_payer,
                "cotisations_salariales": cotisations_salariales,
                "cotisations_patronales": cotisations_patronales,
                "pas": pas,
                "cotisations_detail": cotisations_list,
                "elements_hors_brut": extract_elements_hors_brut(payslip_data),
            }
        )
        totals["total_brut"] += brut
        totals["total_net_a_payer"] += net_a_payer
        totals["total_cotisations_salariales"] += cotisations_salariales
        totals["total_cotisations_patronales"] += cotisations_patronales
        totals["total_pas"] += pas
        totals["employees_count"] += 1

    return payslip_list, totals


def generate_od_salaires(
    company_id: str,
    period: str,
    employee_ids: Optional[List[str]] = None,
    date_ecriture: Optional[str] = None,
    regroupement: str = "global",
) -> Tuple[List[Dict[str, Any]], Dict[str, float], Dict[str, Any]]:
    from app.modules.exports.infrastructure.payroll_ledger import (
        build_payroll_ledger,
        ledger_to_od_export_rows,
    )

    ecritures, od_totals, mappings = build_payroll_ledger(
        company_id,
        period,
        employee_ids,
        date_ecriture,
        regroupement=regroupement,  # type: ignore[arg-type]
        scope="salaires",
    )
    return ledger_to_od_export_rows(ecritures), od_totals, mappings


def generate_od_charges_sociales(
    company_id: str,
    period: str,
    employee_ids: Optional[List[str]] = None,
    date_ecriture: Optional[str] = None,
    regroupement: str = "global",
) -> Tuple[List[Dict[str, Any]], Dict[str, float], Dict[str, Any]]:
    from app.modules.exports.infrastructure.payroll_ledger import (
        build_payroll_ledger,
        ledger_to_od_export_rows,
    )

    ecritures, od_totals, mappings = build_payroll_ledger(
        company_id,
        period,
        employee_ids,
        date_ecriture,
        regroupement=regroupement,  # type: ignore[arg-type]
        scope="charges_sociales",
    )
    return ledger_to_od_export_rows(ecritures), od_totals, mappings


def generate_od_pas(
    company_id: str,
    period: str,
    employee_ids: Optional[List[str]] = None,
    date_ecriture: Optional[str] = None,
    regroupement: str = "global",
) -> Tuple[List[Dict[str, Any]], Dict[str, float], Dict[str, Any]]:
    from app.modules.exports.infrastructure.payroll_ledger import (
        build_payroll_ledger,
        ledger_to_od_export_rows,
    )

    ecritures, od_totals, mappings = build_payroll_ledger(
        company_id,
        period,
        employee_ids,
        date_ecriture,
        regroupement=regroupement,  # type: ignore[arg-type]
        scope="pas",
    )
    return ledger_to_od_export_rows(ecritures), od_totals, mappings


def generate_od_globale(
    company_id: str,
    period: str,
    employee_ids: Optional[List[str]] = None,
    date_ecriture: Optional[str] = None,
    regroupement: str = "global",
) -> Tuple[List[Dict[str, Any]], Dict[str, float], Dict[str, Any]]:
    """OD complète unifiée via le registre paie (sans double comptabilisation)."""
    from app.modules.exports.infrastructure.payroll_ledger import (
        build_payroll_ledger,
        ledger_to_od_export_rows,
    )

    ecritures, od_totals, mappings = build_payroll_ledger(
        company_id,
        period,
        employee_ids,
        date_ecriture,
        regroupement=regroupement,  # type: ignore[arg-type]
        scope="full",
    )
    return ledger_to_od_export_rows(ecritures), od_totals, mappings


def preview_od(
    company_id: str,
    period: str,
    od_type: str,
    employee_ids: Optional[List[str]] = None,
    date_ecriture: Optional[str] = None,
    regroupement: str = "global",
) -> Dict[str, Any]:
    anomalies = []
    warnings = []

    if od_type == "od_salaires":
        ecritures, od_totals, mappings = generate_od_salaires(
            company_id, period, employee_ids, date_ecriture, regroupement
        )
    elif od_type == "od_charges_sociales":
        ecritures, od_totals, mappings = generate_od_charges_sociales(
            company_id, period, employee_ids, date_ecriture, regroupement
        )
    elif od_type == "od_pas":
        ecritures, od_totals, mappings = generate_od_pas(
            company_id, period, employee_ids, date_ecriture, regroupement
        )
    elif od_type == "od_globale":
        ecritures, od_totals, mappings = generate_od_globale(
            company_id, period, employee_ids, date_ecriture, regroupement
        )
    else:
        return {
            "anomalies": [
                {
                    "type": "error",
                    "message": f"Type d'OD non supporté: {od_type}",
                    "severity": "blocking",
                }
            ],
            "can_generate": False,
        }

    if not od_totals["equilibre"]:
        anomalies.append(
            {
                "type": "error",
                "message": f"OD non équilibrée: écart de {od_totals['ecart']:.2f}€",
                "severity": "blocking",
            }
        )
    if len(ecritures) == 0:
        anomalies.append(
            {
                "type": "error",
                "message": "Aucune écriture à générer",
                "severity": "blocking",
            }
        )
    if not mappings:
        warnings.append(
            "Utilisation des mappings par défaut. Configurez vos mappings comptables pour personnaliser."
        )

    _, payslip_totals = get_payslip_data_for_od(
        company_id, period, employee_ids, od_type
    )
    employees_count = int(payslip_totals.get("employees_count") or 0)
    if employees_count == 0:
        anomalies.append(
            {
                "type": "error",
                "message": "Aucun bulletin de paie validé pour cette période",
                "severity": "blocking",
            }
        )

    return {
        "nombre_lignes": len(ecritures),
        "total_debit": od_totals["total_debit"],
        "total_credit": od_totals["total_credit"],
        "equilibre": od_totals["equilibre"],
        "ecart": od_totals["ecart"],
        "balance_debug": od_totals.get("balance_debug"),
        "employees_count": employees_count,
        "totals": payslip_totals,
        "anomalies": anomalies,
        "warnings": warnings,
        "can_generate": len([a for a in anomalies if a.get("severity") == "blocking"])
        == 0,
        "mapping_utilise": mappings,
    }


def generate_od_export_file(
    ecritures: List[Dict[str, Any]],
    od_type: str,
    period: str,
    format: str = "csv",
) -> bytes:
    headers = [
        "Date écriture",
        "Journal",
        "Compte comptable",
        "Libellé",
        "Débit",
        "Crédit",
        "Analytique",
        "Référence export",
        "Période de paie",
    ]
    data = [
        {
            "Date écriture": e["date_ecriture"],
            "Journal": e["journal"],
            "Compte comptable": e["compte_comptable"],
            "Libellé": e["libelle"],
            "Débit": e["debit"],
            "Crédit": e["credit"],
            "Analytique": e.get("analytique", ""),
            "Référence export": e.get("reference_export", ""),
            "Période de paie": e["periode_paie"],
        }
        for e in ecritures
    ]
    type_labels = {
        "od_salaires": "OD Salaires",
        "od_charges_sociales": "OD Charges sociales",
        "od_pas": "OD PAS",
        "od_globale": "OD Globale de paie",
    }
    sheet_name = type_labels.get(od_type, "OD") + f" {format_period(period)}"
    if format == "xlsx":
        return generate_xlsx(data, headers, sheet_name)
    return generate_csv(data, headers)
