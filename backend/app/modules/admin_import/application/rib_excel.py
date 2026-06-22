"""Lecture Excel/CSV et détection colonnes pour import RIB."""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from app.shared.utils.xlsx_safe import iter_sheet_rows

MAX_HEADER_SCAN_ROWS = 25

RIB_COLUMN_ALIASES = (
    "rib",
    "iban",
    "releve identite bancaire",
    "relevé identité bancaire",
    "coordonnees bancaires",
    "coordonnées bancaires",
)

BIC_COLUMN_ALIASES = ("bic", "swift", "code bic")

MATRICULE_ALIASES = (
    "matricule",
    "mat",
    "badge",
    "numero",
    "numéro",
    "time_tracking_id",
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
    "salarié(e)s",
    "salarie",
    "name",
    "employe",
    "employé",
)
EMAIL_ALIASES = ("email", "e-mail", "mail", "courriel")


@dataclass
class TabularSheet:
    headers: List[str] = field(default_factory=list)
    rows: List[Dict[str, str]] = field(default_factory=list)
    header_row_index: int = 0


def _normalize_header(h: str) -> str:
    text = re.sub(r"\s+", " ", (h or "").strip().lower())
    text = text.replace("é", "e").replace("è", "e").replace("ê", "e").replace("à", "a")
    return text


def _match_alias(header: str, aliases: Tuple[str, ...]) -> bool:
    norm = _normalize_header(header)
    if not norm:
        return False
    if norm in aliases:
        return True
    return any(alias in norm for alias in aliases if len(alias) >= 3)


def _is_rib_header_label(header: str) -> bool:
    """True si la cellule ressemble à un intitulé de colonne RIB (pas un titre de document)."""
    norm = _normalize_header(header)
    if not norm:
        return False
    if norm in RIB_COLUMN_ALIASES:
        return True
    for alias in RIB_COLUMN_ALIASES:
        if len(alias) >= 4 and (norm == alias or norm.startswith(f"{alias} ") or norm.endswith(f" {alias}")):
            return True
    return False


def detect_rib_column_mapping(headers: List[str]) -> Dict[str, str]:
    """Retourne mapping logique -> nom de colonne source."""
    mapping: Dict[str, str] = {}
    for header in headers:
        if not header:
            continue
        if "rib" not in mapping and _match_alias(header, RIB_COLUMN_ALIASES):
            mapping["rib"] = header
        elif "bic" not in mapping and _match_alias(header, BIC_COLUMN_ALIASES):
            mapping["bic"] = header
        elif "matricule" not in mapping and _match_alias(header, MATRICULE_ALIASES):
            mapping["matricule"] = header
        elif "last_name" not in mapping and _match_alias(header, LAST_NAME_ALIASES):
            mapping["last_name"] = header
        elif "first_name" not in mapping and _match_alias(header, FIRST_NAME_ALIASES):
            mapping["first_name"] = header
        elif "full_name" not in mapping and _match_alias(header, FULL_NAME_ALIASES):
            mapping["full_name"] = header
        elif "email" not in mapping and _match_alias(header, EMAIL_ALIASES):
            mapping["email"] = header
    return mapping


def _score_header_row(headers: List[str]) -> int:
    mapping = detect_rib_column_mapping(headers)
    rib_header = mapping.get("rib")
    if not rib_header or not _is_rib_header_label(rib_header):
        return 0
    score = 10 + len(mapping) * 2
    non_empty = sum(1 for h in headers if h)
    if non_empty >= 2:
        score += 1
    return score


def find_header_row_index(raw_rows: List[List[str]], *, max_scan: int = MAX_HEADER_SCAN_ROWS) -> Optional[int]:
    """
    Repère la ligne d'en-têtes (ex. ligne 3) en scannant le haut du fichier.
    La ligne doit contenir une colonne RIB/IBAN identifiable.
    """
    best_idx: Optional[int] = None
    best_score = 0
    for idx, row in enumerate(raw_rows[:max_scan]):
        headers = [_cell_str(c) for c in row]
        score = _score_header_row(headers)
        if score > best_score:
            best_score = score
            best_idx = idx
    return best_idx


def _cell_str(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def _rows_to_sheet(raw_rows: List[List[str]], header_idx: int) -> TabularSheet:
    header_cells = [_cell_str(c) for c in raw_rows[header_idx]]
    headers = [h for h in header_cells if h]
    if not headers:
        return TabularSheet(header_row_index=header_idx)

    # Conserver l'index d'origine pour les cellules vides en tête de ligne
    header_pairs = [(i, _cell_str(raw_rows[header_idx][i])) for i in range(len(header_cells))]
    active_pairs = [(i, name) for i, name in header_pairs if name]

    data: List[Dict[str, str]] = []
    for row in raw_rows[header_idx + 1 :]:
        cells = list(row)
        if not any(_cell_str(c) for c in cells):
            continue
        payload: Dict[str, str] = {}
        for col_idx, header in active_pairs:
            payload[header] = _cell_str(cells[col_idx]) if col_idx < len(cells) else ""
        if not any(payload.values()):
            continue
        data.append(payload)

    return TabularSheet(
        headers=[name for _, name in active_pairs],
        rows=data,
        header_row_index=header_idx + 1,
    )


def _read_csv_raw(content: bytes) -> List[List[str]]:
    text = content.decode("utf-8-sig", errors="replace")
    sample = text[:2048]
    delimiter = ";" if sample.count(";") > sample.count(",") else ","
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    return [list(row) for row in reader]


def _read_csv(content: bytes) -> TabularSheet:
    raw_rows = _read_csv_raw(content)
    if not raw_rows:
        return TabularSheet()
    header_idx = find_header_row_index(raw_rows)
    if header_idx is None:
        return _rows_to_sheet(raw_rows, 0)
    return _rows_to_sheet(raw_rows, header_idx)


def _read_xlsx(content: bytes) -> TabularSheet:
    raw_rows: List[List[str]] = iter_sheet_rows(content)
    if not raw_rows:
        return TabularSheet()

    header_idx = find_header_row_index(raw_rows)
    if header_idx is None:
        return _rows_to_sheet(raw_rows, 0)
    return _rows_to_sheet(raw_rows, header_idx)


def read_tabular_file(content: bytes, filename: str) -> TabularSheet:
    lower = (filename or "").lower()
    if lower.endswith(".csv"):
        return _read_csv(content)
    if lower.endswith((".xlsx", ".xls")):
        return _read_xlsx(content)
    raise ValueError("Format non supporté. Utilisez un fichier Excel (.xlsx) ou CSV.")


def row_value(row: Dict[str, str], column: Optional[str]) -> str:
    if not column:
        return ""
    return (row.get(column) or "").strip()
