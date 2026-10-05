# Export FEC (Fichier des Écritures Comptables — arrêté du 29 juillet 2013).
from __future__ import annotations

import io
from calendar import monthrange
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from app.modules.exports.infrastructure.export_formats_cabinet import (
    format_piece_reference,
)
from app.modules.exports.infrastructure.payroll_ledger import (
    assert_ledger_balanced,
    build_payroll_ledger,
    ledger_to_od_export_rows,
)

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


def _montant_fec(valeur: Any) -> str:
    """Montant à la virgule décimale, comme les exemples du BOI-CF-IOR-60-40-20."""
    return f"{float(valeur or 0):.2f}".replace(".", ",")


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
    # Un FEC déséquilibré est rejeté à l'import : autant refuser de le produire.
    assert_ledger_balanced(od_totals)
    ecritures = ledger_to_od_export_rows(ecritures_raw)
    # CompteLib est l'intitulé du compte, le même sur toutes ses lignes : celui
    # de sa première ligne dans l'OD (« Net à payer » pour le 421).
    intitule_du_compte: Dict[str, str] = {}
    for brute in ecritures_raw:
        intitule_du_compte.setdefault(
            str(brute.get("compte_comptable", "")),
            str(brute.get("compte_lib") or brute.get("libelle") or ""),
        )
    fec_date = _fec_date(period, date_ecriture)
    valid_date = datetime.now().strftime("%Y%m%d")
    ecriture_num = f"PAIE{period.replace('-', '')}"
    # Référence de pièce au format du cabinet (PAIE + MMAA), relevée sur son OD.
    piece_ref = format_piece_reference(period)
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
                "CompteLib": intitule_du_compte.get(compte, "")[:50],
                "CompAuxNum": "",
                "CompAuxLib": "",
                "PieceRef": piece_ref,
                "PieceDate": fec_date,
                "EcritureLib": str(e.get("libelle", ""))[:200],
                "Debit": _montant_fec(e.get("debit")),
                "Credit": _montant_fec(e.get("credit")),
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
