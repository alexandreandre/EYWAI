# Export FEC (Fichier des Écritures Comptables — arrêté du 29 juillet 2013).
from __future__ import annotations

import io
from calendar import monthrange
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from app.modules.exports.infrastructure.payroll_ledger import (
    build_payroll_ledger,
    ledger_to_od_export_rows,
)
from app.shared.utils.export import format_period

FEC_COLUMNS = [
    "JournalCode",
    "JournalLib",
    "EcritureNum",
    "EcritureDate",
    "CompteNum",
    "CompteLib",
    "CompAuxNum",
    "CompAuxLib",
    "PieceRef",
    "PieceDate",
    "EcritureLib",
    "Debit",
    "Credit",
    "EcritureLet",
    "DateLet",
    "ValidDate",
    "Montantdevise",
    "Idevise",
]


def _fec_date(period: str, date_ecriture: Optional[str] = None) -> str:
    if date_ecriture:
        return date_ecriture.replace("-", "")
    year, month = map(int, period.split("-"))
    last_day = monthrange(year, month)[1]
    return f"{year:04d}{month:02d}{last_day:02d}"


def build_fec_rows(
    company_id: str,
    period: str,
    employee_ids: Optional[List[str]] = None,
    date_ecriture: Optional[str] = None,
    company_siret: str = "",
) -> Tuple[List[Dict[str, str]], Dict[str, Any], Optional[Dict[str, Any]]]:
    ecritures_raw, od_totals, _ = build_payroll_ledger(
        company_id, period, employee_ids, date_ecriture, scope="full"
    )
    ecritures = ledger_to_od_export_rows(ecritures_raw)
    fec_date = _fec_date(period, date_ecriture)
    valid_date = datetime.now().strftime("%Y%m%d")
    ecriture_num = f"PAIE{period.replace('-', '')}"
    rows: List[Dict[str, str]] = []

    for idx, e in enumerate(ecritures, start=1):
        journal = str(e.get("journal", "OD"))
        compte = str(e.get("compte_comptable", ""))
        rows.append(
            {
                "JournalCode": journal,
                "JournalLib": f"Journal {journal}",
                "EcritureNum": ecriture_num,
                "EcritureDate": fec_date,
                "CompteNum": compte,
                "CompteLib": str(e.get("libelle", ""))[:50],
                "CompAuxNum": "",
                "CompAuxLib": "",
                "PieceRef": str(e.get("reference_export", "")),
                "PieceDate": fec_date,
                "EcritureLib": str(e.get("libelle", ""))[:200],
                "Debit": f"{float(e.get('debit', 0) or 0):.2f}",
                "Credit": f"{float(e.get('credit', 0) or 0):.2f}",
                "EcritureLet": "",
                "DateLet": "",
                "ValidDate": valid_date,
                "Montantdevise": "",
                "Idevise": "",
            }
        )

    totals = {
        "employees_count": 0,
        "total_amount": od_totals.get("total_debit", 0),
        "lines_count": len(rows),
        "equilibre": od_totals.get("equilibre", False),
    }
    return rows, totals, od_totals.get("balance_debug")


def generate_fec_export(
    company_id: str,
    period: str,
    employee_ids: Optional[List[str]] = None,
    date_ecriture: Optional[str] = None,
    company_siret: str = "",
) -> bytes:
    rows, _, _ = build_fec_rows(
        company_id, period, employee_ids, date_ecriture, company_siret
    )
    output = io.StringIO()
    output.write("\t".join(FEC_COLUMNS) + "\n")
    for row in rows:
        output.write("\t".join(row.get(col, "") for col in FEC_COLUMNS) + "\n")
    return output.getvalue().encode("utf-8")


def preview_fec(
    company_id: str,
    period: str,
    employee_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    rows, totals, balance_debug = build_fec_rows(company_id, period, employee_ids)
    anomalies: List[Dict[str, Any]] = []
    warnings: List[str] = []
    if not rows:
        warnings.append("Aucune écriture comptable pour cette période.")
    if not totals.get("equilibre"):
        anomalies.append(
            {
                "type": "error",
                "message": "Écritures non équilibrées — FEC invalide",
                "severity": "blocking",
            }
        )
    return {
        "employees_count": totals.get("employees_count", 0),
        "totals": totals,
        "anomalies": anomalies,
        "warnings": warnings,
        "can_generate": len(anomalies) == 0,
        "details": {
            "lines_count": len(rows),
            "balance_debug": balance_debug,
        },
        "balance_debug": balance_debug,
    }
