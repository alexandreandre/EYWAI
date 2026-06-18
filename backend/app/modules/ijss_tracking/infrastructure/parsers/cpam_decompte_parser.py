"""Parseur décomptes CPAM (CSV export Net-Entreprises)."""

from __future__ import annotations

import csv
import io
import re
from typing import Any, Dict, List, Optional, Tuple

from app.modules.ijss_tracking.infrastructure.parsers.bank_recap_parser import (
    _parse_amount,
    _parse_date,
    detect_column_mapping,
)


CPAM_COLUMN_ALIASES = {
    "payment_date": ("date paiement", "date", "date versement"),
    "amount": ("montant ij", "montant", "ijss", "indemnites", "indemnités"),
    "employee_name": ("nom", "assure", "assuré", "salarié", "salarié"),
    "employee_nir": ("nir", "nss", "numero ss"),
    "period_start": ("debut", "début", "period_start"),
    "period_end": ("fin", "period_end"),
}


def detect_cpam_column_mapping(headers: List[str]) -> Dict[str, str]:
    mapping: Dict[str, str] = {}
    norm = {h.strip().lower(): h for h in headers if h}
    for field, aliases in CPAM_COLUMN_ALIASES.items():
        for alias in aliases:
            if alias in norm:
                mapping[field] = norm[alias]
                break
    if not mapping:
        mapping = detect_column_mapping(headers)
    return mapping


def parse_cpam_decompte_file(
    filename: str,
    content: bytes,
    column_mapping: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    text = content.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text), delimiter=";")
    if not reader.fieldnames:
        reader = csv.DictReader(io.StringIO(text), delimiter=",")
    headers = list(reader.fieldnames or [])
    raw_rows = list(reader)
    mapping = column_mapping or detect_cpam_column_mapping(headers)
    lines: List[Dict[str, Any]] = []
    anomalies: List[str] = []

    for i, row in enumerate(raw_rows):
        amount_col = mapping.get("amount")
        amt = _parse_amount(row.get(amount_col)) if amount_col else None
        if amt is None or amt <= 0:
            anomalies.append(f"Ligne {i + 1}: montant IJ invalide")
            continue
        lines.append(
            {
                "row_index": i,
                "amount": amt,
                "payment_date": _parse_date(row.get(mapping.get("payment_date", "")))
                if mapping.get("payment_date")
                else None,
                "employee_name_raw": str(row.get(mapping.get("employee_name", "")) or "").strip(),
                "employee_nir": str(row.get(mapping.get("employee_nir", "")) or "").strip(),
                "period_start": _parse_date(row.get(mapping.get("period_start", "")))
                if mapping.get("period_start")
                else None,
                "period_end": _parse_date(row.get(mapping.get("period_end", "")))
                if mapping.get("period_end")
                else None,
                "raw": dict(row),
            }
        )

    return {
        "headers": headers,
        "detected_mapping": mapping,
        "lines": lines,
        "anomalies": anomalies,
        "line_count": len(lines),
    }
