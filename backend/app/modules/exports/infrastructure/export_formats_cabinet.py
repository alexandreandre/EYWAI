# Formats cabinet comptable (générique, Quadra natif, Sage natif).
from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.shared.utils.export import format_period, generate_csv, generate_xlsx

from .payroll_ledger import build_payroll_ledger, ledger_to_od_export_rows


def _ledger_ecritures(
    company_id: str,
    period: str,
    employee_ids: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    ecritures, _, _ = build_payroll_ledger(
        company_id, period, employee_ids, scope="full"
    )
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
    sheet_name = f"Export Cabinet {format_period(period)}"
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
    ecritures = _ledger_ecritures(company_id, period, employee_ids)
    total_debit = sum(e["debit"] for e in ecritures)
    total_credit = sum(e["credit"] for e in ecritures)
    equilibre = abs(total_debit - total_credit) < 0.01
    return {
        "nombre_lignes": len(ecritures),
        "total_debit": round(total_debit, 2),
        "total_credit": round(total_credit, 2),
        "equilibre": equilibre,
        "ecart": round(abs(total_debit - total_credit), 2),
        "anomalies": [] if equilibre and ecritures else [
            {
                "type": "error",
                "message": "OD non équilibrée ou vide",
                "severity": "blocking",
            }
        ],
        "warnings": [],
        "can_generate": equilibre and len(ecritures) > 0,
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
