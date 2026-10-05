# Formats cabinet comptable (générique, Quadra natif, Sage natif).
from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.shared.utils.export import format_period, generate_csv, generate_xlsx

from .export_ecritures_comptables import get_payslip_data_for_od
from .payroll_ledger import (
    assert_ledger_balanced,
    build_payroll_ledger,
    ledger_to_od_export_rows,
)


def _ledger_ecritures(
    company_id: str,
    period: str,
    employee_ids: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """Écritures de l'OD complète ; refusées si elles ne s'équilibrent pas.

    Un fichier déséquilibré est rejeté à l'import par le logiciel comptable :
    mieux vaut le refuser ici, avec le détail de ce qui manque.
    """
    ecritures, od_totals, _ = build_payroll_ledger(
        company_id, period, employee_ids, scope="full"
    )
    assert_ledger_balanced(od_totals)
    return ledger_to_od_export_rows(ecritures)


def generate_cabinet_generic_export(
    company_id: str,
    period: str,
    employee_ids: Optional[List[str]] = None,
    format: str = "csv",
) -> bytes:
    all_ecritures = _ledger_ecritures(company_id, period, employee_ids)
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
    sheet_name = f"Export comptable {format_period(period)}"
    if format == "xlsx":
        return generate_xlsx(data, headers, sheet_name)
    return generate_csv(data, headers)


def _format_quadra_line(ecriture: Dict[str, Any]) -> str:
    """Format ASCII Quadra/Cegid — enregistrement M (mouvement)."""
    date_str = str(ecriture["date_ecriture"]).replace("-", "")
    journal = str(ecriture.get("journal", "OD"))[:3].ljust(3)
    compte = str(ecriture.get("compte_comptable", ""))[:8].ljust(8)
    libelle = str(ecriture.get("libelle", ""))[:30].ljust(30)
    debit = f"{float(ecriture.get('debit', 0) or 0):015.2f}"
    credit = f"{float(ecriture.get('credit', 0) or 0):015.2f}"
    analytique = str(ecriture.get("analytique") or "")[:6].ljust(6)
    return f"M{journal}{date_str}{compte}{libelle}{debit}{credit}{analytique}"


def generate_cabinet_quadra_export(
    company_id: str,
    period: str,
    employee_ids: Optional[List[str]] = None,
    format: str = "csv",
) -> bytes:
    all_ecritures = _ledger_ecritures(company_id, period, employee_ids)
    lines = [_format_quadra_line(e) for e in all_ecritures]
    content = "\r\n".join(lines) + "\r\n"
    return content.encode("latin-1", errors="replace")


def _format_sage_line(ecriture: Dict[str, Any]) -> str:
    """Format import Sage 100 — journal pipe-delimited."""
    date_str = str(ecriture["date_ecriture"]).replace("-", "")
    fields = [
        date_str,
        str(ecriture.get("journal", "OD")),
        str(ecriture.get("compte_comptable", "")),
        str(ecriture.get("libelle", ""))[:35],
        f"{float(ecriture.get('debit', 0) or 0):.2f}",
        f"{float(ecriture.get('credit', 0) or 0):.2f}",
        str(ecriture.get("analytique") or ""),
        str(ecriture.get("reference_export", "")),
    ]
    return "|".join(fields)


def generate_cabinet_sage_export(
    company_id: str,
    period: str,
    employee_ids: Optional[List[str]] = None,
    format: str = "csv",
) -> bytes:
    all_ecritures = _ledger_ecritures(company_id, period, employee_ids)
    lines = [_format_sage_line(e) for e in all_ecritures]
    header = "Date|Journal|Compte|Libelle|Debit|Credit|Analytique|Reference"
    content = header + "\r\n" + "\r\n".join(lines) + "\r\n"
    return content.encode("utf-8-sig")


def preview_cabinet_export(
    company_id: str,
    period: str,
    export_type: str,
    employee_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    ecritures, od_totals, _ = build_payroll_ledger(
        company_id, period, employee_ids, scope="full"
    )
    _, totaux_bulletins = get_payslip_data_for_od(company_id, period, employee_ids)
    employees_count = int(totaux_bulletins.get("employees_count") or 0)
    equilibre = bool(od_totals.get("equilibre"))

    anomalies: List[Dict[str, Any]] = []
    if not ecritures:
        anomalies.append(
            {"type": "error", "message": "Aucune écriture à exporter", "severity": "blocking"}
        )
    if not equilibre:
        anomalies.append(
            {
                "type": "error",
                "message": f"OD non équilibrée : écart de {od_totals.get('ecart', 0):.2f} €",
                "severity": "blocking",
            }
        )
        for anomalie in od_totals.get("anomalies") or []:
            anomalies.append(
                {
                    "type": "error",
                    "message": f"{anomalie.get('label', '')} : {anomalie.get('detail', '')}",
                    "severity": "blocking",
                }
            )
    return {
        "employees_count": employees_count,
        "totals": {
            "employees_count": employees_count,
            "total_brut": totaux_bulletins.get("total_brut"),
            "total_net_a_payer": totaux_bulletins.get("total_net_a_payer"),
            "total_cotisations_salariales": totaux_bulletins.get("total_cotisations_salariales"),
            "total_cotisations_patronales": totaux_bulletins.get("total_cotisations_patronales"),
            "total_amount": od_totals.get("total_debit", 0),
        },
        "nombre_lignes": len(ecritures),
        "total_debit": od_totals.get("total_debit", 0),
        "total_credit": od_totals.get("total_credit", 0),
        "equilibre": equilibre,
        "ecart": od_totals.get("ecart", 0),
        "anomalies": anomalies,
        "warnings": [],
        "can_generate": equilibre and bool(ecritures),
    }


def format_piece_reference(period: str) -> str:
    """Référence de pièce au format du cabinet : PAIE + MMAA.

    Relevé sur l'OD de paie de référence : période 10/2025 → PAIE1025.
    """
    year, month = period.split("-")
    return f"PAIE{month}{year[2:]}"


def format_libelle_ecriture(period: str) -> str:
    """Libellé d'écriture au format du cabinet : « Salaire de MM/AAAA »."""
    year, month = period.split("-")
    return f"Salaire de {month}/{year}"
