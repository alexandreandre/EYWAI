"""Lecture Excel/CSV et détection colonnes pour import dates d'ancienneté."""

from __future__ import annotations

import re
from typing import Dict, List, Optional

from app.modules.admin_import.application.rib_excel import (
    MAX_HEADER_SCAN_ROWS,
    TabularSheet,
    _cell_str,
    _match_alias,
    _normalize_header,
    _rows_to_sheet,
    row_value,
)

LAST_NAME_ALIASES = ("nom", "lastname")
FIRST_NAME_ALIASES = ("prenom", "prénom", "firstname")
FULL_NAME_ALIASES = (
    "nom prenom",
    "nom prénom",
    "nom et prenom",
    "nom complet",
    "identite",
    "identité",
    "salarié",
    "salarié(e)",
    "salarie",
    "name",
)
MATRICULE_ALIASES = (
    "matricule",
    "mat",
    "badge",
    "numero",
    "numéro",
    "time_tracking_id",
)
SENIORITY_DATE_ALIASES = (
    "date anciennete",
    "date d anciennete",
    "date d'anciennete",
    "date reprise",
    "anciennete",
)
STATUT_ALIASES = ("statut", "status")
CLASSE_ALIASES = (
    "conv niveau",
    "classe",
    "niveau",
    "classification",
    "coefficient",
)


def _is_seniority_date_header(header: str) -> bool:
    norm = _normalize_header(header)
    if not norm:
        return False
    if norm in SENIORITY_DATE_ALIASES:
        return True
    if "date" in norm and "anciennet" in norm:
        return True
    return False


def detect_seniority_column_mapping(headers: List[str]) -> Dict[str, str]:
    mapping: Dict[str, str] = {}
    for header in headers:
        if not header:
            continue
        norm = _normalize_header(header)
        if "seniority_date" not in mapping and _is_seniority_date_header(header):
            mapping["seniority_date"] = header
        elif "last_name" not in mapping and _match_alias(header, LAST_NAME_ALIASES):
            mapping["last_name"] = header
        elif "first_name" not in mapping and _match_alias(header, FIRST_NAME_ALIASES):
            mapping["first_name"] = header
        elif "full_name" not in mapping and _match_alias(header, FULL_NAME_ALIASES):
            mapping["full_name"] = header
        elif "matricule" not in mapping and _match_alias(header, MATRICULE_ALIASES):
            mapping["matricule"] = header
        elif "statut" not in mapping and _match_alias(header, STATUT_ALIASES):
            mapping["statut"] = header
        elif "classe" not in mapping and _match_alias(header, CLASSE_ALIASES):
            mapping["classe"] = header
    return mapping


def _score_seniority_header_row(headers: List[str]) -> int:
    mapping = detect_seniority_column_mapping(headers)
    date_header = mapping.get("seniority_date")
    if not date_header or not _is_seniority_date_header(date_header):
        return 0
    score = 10 + len(mapping) * 2
    if mapping.get("last_name") or mapping.get("first_name"):
        score += 3
    non_empty = sum(1 for h in headers if h)
    if non_empty >= 3:
        score += 1
    return score


def find_seniority_header_row_index(
    raw_rows: List[List[str]],
    *,
    max_scan: int = MAX_HEADER_SCAN_ROWS,
) -> Optional[int]:
    best_idx: Optional[int] = None
    best_score = 0
    for idx, row in enumerate(raw_rows[:max_scan]):
        headers = [_cell_str(c) for c in row]
        score = _score_seniority_header_row(headers)
        if score > best_score:
            best_score = score
            best_idx = idx
    return best_idx


def read_seniority_tabular_file(content: bytes, filename: str) -> TabularSheet:
    lower = (filename or "").lower()
    if lower.endswith(".csv"):
        from app.modules.admin_import.application.rib_excel import _read_csv_raw

        raw_rows = _read_csv_raw(content)
    elif lower.endswith((".xlsx", ".xls")):
        from app.shared.utils.xlsx_safe import iter_sheet_rows

        raw_rows = iter_sheet_rows(content)
    else:
        raise ValueError("Format non supporté. Utilisez un fichier Excel (.xlsx) ou CSV.")

    if not raw_rows:
        return TabularSheet()

    header_idx = find_seniority_header_row_index(raw_rows)
    if header_idx is None:
        return _rows_to_sheet(raw_rows, 0)
    return _rows_to_sheet(raw_rows, header_idx)


def parse_seniority_date_cell(value: str) -> Optional[str]:
    """Parse une date d'ancienneté (française ou ISO)."""
    from app.modules.admin_import.application.payroll_export_parser import (
        parse_french_date,
    )

    raw = (value or "").strip()
    if not raw:
        return None
    parsed = parse_french_date(raw)
    if parsed:
        return parsed
    if re.fullmatch(r"\d{5}(\.\d+)?", raw):
        try:
            from datetime import date, timedelta

            serial = float(raw)
            if serial > 10000:
                base = date(1899, 12, 30)
                return (base + timedelta(days=int(serial))).isoformat()
        except (TypeError, ValueError, OverflowError):
            return None
    return None


__all__ = [
    "detect_seniority_column_mapping",
    "parse_seniority_date_cell",
    "read_seniority_tabular_file",
    "row_value",
]
