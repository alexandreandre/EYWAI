# Export « Paiement organismes » — échéances URSSAF, retraite, mutuelle, prévoyance.
from __future__ import annotations

import io
from typing import Any, Dict, List, Optional

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill

from app.core.database import supabase
from app.modules.exports.infrastructure.export_charges_sociales import (
    get_charges_sociales_data,
)
from app.shared.domain.effectif_seuils import effectif_retenu
from app.shared.utils.export import generate_csv

#: Seuil de l'échéance Urssaf : sous 50 salariés, les cotisations de M se paient le 15 de M+1.
SEUIL_ECHEANCE_MENSUELLE = 50

HEADERS = [
    "Organisme",
    "Libellé cotisation",
    "Part salariale",
    "Part patronale",
    "Total à payer",
    "Échéance",
    "Référence paiement",
    "IBAN organisme",
]


def _charger_societe(company_id: str) -> Dict[str, Any]:
    """Effectif et réglages de la société (lecture seule)."""
    reponse = (
        supabase.table("companies")
        .select("effectif, settings")
        .eq("id", company_id)
        .execute()
    )
    lignes = reponse.data or []
    return lignes[0] if lignes else {}


def _effectif_des_seuils(company_id: str, period: str) -> int:
    """L'effectif des seuils de l'année de la période (saisi dans les paramètres de paie)."""
    annee = int(period.split("-")[0])
    return effectif_retenu(_charger_societe(company_id), annee).valeur


def _echeance(period: str, effectif: int) -> str:
    """Sous 50 salariés : le 15 du mois suivant. À 50 et plus : inchangée (le 15 du
    mois de paie), en attendant la décision sur le 5 ou le 15 de M+1."""
    year, month = map(int, period.split("-"))
    if effectif < SEUIL_ECHEANCE_MENSUELLE:
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return f"{year}-{month:02d}-15"


def _build_payment_rows(
    detail_rows: List[Dict[str, Any]],
    period: str,
    effectif: int,
) -> List[Dict[str, Any]]:
    echeance = _echeance(period, effectif)
    rows: List[Dict[str, Any]] = []
    for item in detail_rows:
        total = float(item.get("Total cotisations", 0) or 0)
        # Une réduction (réduction générale, déduction heures sup.) est
        # négative : la sauter ferait payer l'organisme sans elle.
        if total == 0:
            continue
        org = item.get("Organisme", "AUTRE")
        rows.append(
            {
                "Organisme": org,
                "Libellé cotisation": item.get("Libellé cotisation", ""),
                "Part salariale": item.get("Part salariale", 0),
                "Part patronale": item.get("Part patronale", 0),
                "Total à payer": round(total, 2),
                "Échéance": echeance,
                "Référence paiement": f"ORG-{period}-{org}",
                "IBAN organisme": "",
            }
        )
    return rows


def preview_paiement_organismes(
    company_id: str,
    period: str,
    employee_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    detail_rows, summary_rows, totals = get_charges_sociales_data(
        company_id, period, employee_ids
    )
    effectif = _effectif_des_seuils(company_id, period)
    payment_rows = _build_payment_rows(detail_rows, period, effectif)
    warnings: List[str] = []
    if effectif >= SEUIL_ECHEANCE_MENSUELLE:
        warnings.append(
            "Société de 50 salariés ou plus : l'échéance (le 15 du mois de paie) est à "
            "confirmer, la date dépend de la date de paiement des salaires."
        )
    if not payment_rows:
        warnings.append("Aucune cotisation à payer pour cette période.")
    return {
        "employees_count": totals.get("employees_count", 0),
        "totals": {
            **totals,
            "operations_count": len(payment_rows),
            "total_amount": sum(r["Total à payer"] for r in payment_rows),
        },
        "anomalies": [],
        "warnings": warnings,
        "can_generate": True,
        "details": {"lines": payment_rows, "organismes": summary_rows},
    }


def generate_paiement_organismes_export(
    company_id: str,
    period: str,
    employee_ids: Optional[List[str]] = None,
    file_format: str = "xlsx",
) -> bytes:
    detail_rows, _, _ = get_charges_sociales_data(
        company_id, period, employee_ids
    )
    rows = _build_payment_rows(detail_rows, period, _effectif_des_seuils(company_id, period))
    if file_format == "xlsx":
        wb = Workbook()
        ws = wb.active
        ws.title = "Paiement organismes"
        header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
        for col_idx, h in enumerate(HEADERS, start=1):
            cell = ws.cell(row=1, column=col_idx, value=h)
            cell.fill = header_fill
            cell.font = Font(bold=True, color="FFFFFF")
        for row_idx, row in enumerate(rows, start=2):
            for col_idx, h in enumerate(HEADERS, start=1):
                ws.cell(row=row_idx, column=col_idx, value=row.get(h, ""))
        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        return output.read()
    return generate_csv(rows, HEADERS)
