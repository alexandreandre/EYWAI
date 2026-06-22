"""Parseur tabulaire générique CSV/XLSX pour import pointages."""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from app.shared.utils.xlsx_safe import iter_sheet_rows

MAX_HEADER_SCAN_ROWS = 25


DEFAULT_COLUMN_ALIASES = {
    "matricule": (
        "matricule",
        "mat",
        "id",
        "badge",
        "numero",
        "numéro",
        "time_tracking_id",
    ),
    "last_name": ("nom", "lastname", "name", "salarié", "salarié(e)", "salarie"),
    "first_name": ("prenom", "prénom", "firstname"),
    "full_name": (
        "nom prenom",
        "nom prénom",
        "nom complet",
        "identite",
        "identité",
        "employe",
        "employé",
    ),
    "date": ("date", "jour", "day", "date_pointage", "date pointage"),
    "hours": (
        "heures",
        "hours",
        "duree",
        "durée",
        "temps",
        "total",
        "heures_faites",
        "tot h poin",
        "tot h",
        "total heures",
        "heures pointees",
        "heures pointées",
    ),
    "entry_1": (
        "entree 1",
        "entrée 1",
        "entree1",
        "entry_1",
        "entry1",
        "entree_1",
        "entree",
        "heure entree",
        "heure entrée",
    ),
    "exit_last": (
        "sortie 3",
        "sortie3",
        "exit_last",
        "exit_3",
        "sortie_3",
        "derniere sortie",
        "dernière sortie",
        "sortie finale",
    ),
    "exit_2": ("sortie 2", "sortie2", "exit_2", "exit2"),
    "exit_1": ("sortie 1", "sortie1", "exit_1", "exit1"),
    "shift_code": (
        "code horai",
        "code horaire",
        "shift_code",
        "code_horaire",
    ),
}


@dataclass
class TabularDayRow:
    matricule: Optional[str] = None
    raw_name: Optional[str] = None
    jour: int = 0
    month: int = 0
    year: int = 0
    heures: float = 0.0
    entry_raw: object = None
    exit_raw: object = None
    shift_code: Optional[str] = None
    raw_payload: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TabularParseResult:
    confidence: float = 0.0
    rows: List[TabularDayRow] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    headers: List[str] = field(default_factory=list)
    column_mapping: Dict[str, str] = field(default_factory=dict)


def _normalize_header(h: str) -> str:
    text = re.sub(r"\s+", " ", (h or "").strip().lower())
    text = text.replace("é", "e").replace("è", "e").replace("ê", "e").replace("à", "a")
    text = re.sub(r"[.\s]+$", "", text)
    return text


def _match_alias(header: str, aliases: Tuple[str, ...]) -> bool:
    norm = _normalize_header(header)
    if not norm:
        return False
    if norm in aliases:
        return True
    return any(alias in norm for alias in aliases if len(alias) >= 3)


def detect_column_mapping(headers: List[str]) -> Dict[str, str]:
    mapping: Dict[str, str] = {}
    for header in headers:
        if not header:
            continue
        for field_name, aliases in DEFAULT_COLUMN_ALIASES.items():
            if field_name in mapping:
                continue
            if _match_alias(header, aliases):
                mapping[field_name] = header
                break
    return mapping


def is_mapping_sufficient(mapping: Dict[str, str]) -> bool:
    """True si le mapping auto permet de parser sans intervention manuelle."""
    if not mapping.get("date"):
        return False
    if mapping.get("hours"):
        return True
    return bool(mapping.get("entry_1") and mapping.get("exit_last"))


def _score_header_row(headers: List[str]) -> int:
    mapping = detect_column_mapping(headers)
    if not mapping:
        return 0
    score = len(mapping) * 2
    if mapping.get("entry_1") and mapping.get("exit_last"):
        score += 10
    elif mapping.get("hours"):
        score += 8
    if mapping.get("date"):
        score += 5
    if mapping.get("matricule") or mapping.get("last_name") or mapping.get("first_name"):
        score += 3
    non_empty = sum(1 for h in headers if h)
    if non_empty >= 3:
        score += 1
    return score


def find_header_row_index(
    raw_rows: List[List[Any]], *, max_scan: int = MAX_HEADER_SCAN_ROWS
) -> Optional[int]:
    """Repère la ligne d'en-têtes en scannant le haut du fichier."""
    best_idx: Optional[int] = None
    best_score = 0
    for idx, row in enumerate(raw_rows[:max_scan]):
        headers = [_cell_str(c) for c in row]
        score = _score_header_row(headers)
        if score > best_score:
            best_score = score
            best_idx = idx
    if best_idx is not None and best_score >= 8:
        return best_idx
    return None


def _cell_str(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def _rows_from_raw(
    raw_rows: List[List[Any]], header_idx: int
) -> Tuple[List[str], List[Dict[str, Any]]]:
    if not raw_rows or header_idx >= len(raw_rows):
        return [], []
    header_cells = [_cell_str(c) for c in raw_rows[header_idx]]
    header_pairs = [(i, name) for i, name in enumerate(header_cells) if name]
    if not header_pairs:
        return [], []

    headers = [name for _, name in header_pairs]
    rows: List[Dict[str, Any]] = []
    for row in raw_rows[header_idx + 1 :]:
        cells = list(row) if row else []
        if not any(_cell_str(c) for c in cells):
            continue
        payload: Dict[str, Any] = {}
        for col_idx, header in header_pairs:
            payload[header] = cells[col_idx] if col_idx < len(cells) else None
        if not any(v is not None and _cell_str(v) for v in payload.values()):
            continue
        rows.append(payload)
    return headers, rows


def _read_csv_raw(content: bytes, delimiter: str | None = None) -> List[List[str]]:
    for enc in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            text = content.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        text = content.decode("utf-8", errors="replace")

    if delimiter is None:
        sample = text[:2048]
        delimiter = ";" if sample.count(";") > sample.count(",") else ","

    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    return [list(row) for row in reader]


def _rows_from_csv(content: bytes, delimiter: str | None = None) -> Tuple[List[str], List[Dict[str, Any]]]:
    raw_rows = _read_csv_raw(content, delimiter)
    if not raw_rows:
        return [], []
    header_idx = find_header_row_index(raw_rows)
    if header_idx is None:
        header_idx = 0
    return _rows_from_raw(raw_rows, header_idx)


def _rows_from_xlsx(content: bytes, sheet_name: str | None = None) -> Tuple[List[str], List[Dict[str, Any]]]:
    raw_rows: List[List[Any]] = iter_sheet_rows(content, sheet_name=sheet_name)
    if not raw_rows:
        return [], []
    header_idx = find_header_row_index(raw_rows)
    if header_idx is None:
        header_idx = 0
    return _rows_from_raw(raw_rows, header_idx)


def read_tabular_preview(
    content: bytes,
    filename: str,
    *,
    max_rows: int = 5,
    options: Optional[Dict[str, Any]] = None,
) -> Tuple[List[str], List[Dict[str, Any]], Dict[str, str]]:
    opts = options or {}
    lower = (filename or "").lower()
    skip_rows = int(opts.get("skip_rows") or 0)
    if lower.endswith((".xlsx", ".xls")):
        headers, rows = _rows_from_xlsx(content, opts.get("sheet_name"))
    else:
        headers, rows = _rows_from_csv(content, opts.get("delimiter"))
    if skip_rows:
        rows = rows[skip_rows:]
    mapping = detect_column_mapping(headers)
    return headers, rows[:max_rows], mapping


def read_tabular_preview_with_status(
    content: bytes,
    filename: str,
    *,
    max_rows: int = 5,
    options: Optional[Dict[str, Any]] = None,
) -> Tuple[List[str], List[Dict[str, Any]], Dict[str, str], bool]:
    headers, rows, mapping = read_tabular_preview(
        content, filename, max_rows=max_rows, options=options
    )
    return headers, rows, mapping, is_mapping_sufficient(mapping)


def _parse_hours(raw: Any, *, decimal_separator: str = ".") -> Optional[float]:
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return round(float(raw), 2)
    original = str(raw).strip().lower().replace(" ", "")
    if not original or original in ("-", "—"):
        return None

    # Export Cegid : heures décimales avec virgule (7,05) — pas une heure HH:MM
    french_decimal = "," in original and "." not in original
    if french_decimal or decimal_separator == ",":
        dec = original.replace(",", ".")
        dec = re.sub(r"[^\d.\-]", "", dec)
        if dec:
            try:
                val = float(dec)
                if 0 <= val <= 24:
                    return round(val, 2)
            except ValueError:
                pass

    s = original
    if decimal_separator == ",":
        s = s.replace(",", ".")
    m = re.match(r"^(\d+)[:h.](\d{2})$", s)
    if m:
        return round(int(m.group(1)) + int(m.group(2)) / 60.0, 2)
    m = re.match(r"^(\d{1,2})h(\d{2})?$", s)
    if m:
        mins = int(m.group(2) or 0)
        return round(int(m.group(1)) + mins / 60.0, 2)
    s = re.sub(r"[^\d.\-]", "", s)
    if not s:
        return None
    try:
        val = float(s)
        return round(val, 2) if 0 <= val <= 24 else None
    except ValueError:
        return None


def _parse_date_value(
    raw: Any,
    *,
    date_format: str | None,
    default_year: int,
    default_month: int,
) -> Optional[Tuple[int, int, int]]:
    if raw is None:
        return None
    if hasattr(raw, "date"):
        d = raw.date() if hasattr(raw, "date") else raw
        return d.year, d.month, d.day
    if isinstance(raw, (int, float)) and raw > 30000:
        base = date(1899, 12, 30)
        d = base + timedelta(days=int(raw))
        return d.year, d.month, d.day
    s = str(raw).strip()
    formats = [date_format] if date_format else []
    formats.extend(["%d/%m/%Y", "%Y-%m-%d", "%d/%m/%y", "%d-%m-%Y"])
    for fmt in formats:
        if not fmt:
            continue
        try:
            d = datetime.strptime(s[:10], fmt).date()
            return d.year, d.month, d.day
        except ValueError:
            continue
    m = re.match(r"^(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?$", s)
    if m:
        day, mon = int(m.group(1)), int(m.group(2))
        y_raw = m.group(3)
        year = default_year
        if y_raw:
            year = int(y_raw)
            if year < 100:
                year += 2000
        return year, mon, day
    if s.isdigit() and 1 <= int(s) <= 31:
        return default_year, default_month, int(s)
    return None


def parse_tabular_file(
    content: bytes,
    filename: str,
    *,
    target_year: int,
    target_month: int,
    column_mapping: Optional[Dict[str, str]] = None,
    options: Optional[Dict[str, Any]] = None,
) -> TabularParseResult:
    opts = options or {}
    lower = (filename or "").lower()
    skip_rows = int(opts.get("skip_rows") or 0)

    if lower.endswith((".xlsx", ".xls")):
        headers, raw_rows = _rows_from_xlsx(content, opts.get("sheet_name"))
    else:
        headers, raw_rows = _rows_from_csv(content, opts.get("delimiter"))

    if skip_rows:
        raw_rows = raw_rows[skip_rows:]

    mapping = column_mapping or detect_column_mapping(headers)
    result = TabularParseResult(headers=headers, column_mapping=mapping)

    entry_col = mapping.get("entry_1")
    exit_col = mapping.get("exit_last")
    punch_pairs_mode = bool(entry_col and exit_col)

    if not punch_pairs_mode and not mapping.get("hours") and not mapping.get("date"):
        result.warnings.append(
            "Colonnes heures ou date non détectées — vérifiez le mapping."
        )
        return result

    date_col = mapping.get("date")
    hours_col = mapping.get("hours")
    mat_col = mapping.get("matricule")
    last_col = mapping.get("last_name")
    first_col = mapping.get("first_name")
    full_name_col = mapping.get("full_name")
    shift_col = mapping.get("shift_code")
    exit_2_col = mapping.get("exit_2")
    exit_1_col = mapping.get("exit_1")
    use_last_exit = bool(opts.get("use_last_nonzero_exit", True))

    decimal_sep = str(opts.get("decimal_separator") or "")
    if not decimal_sep and hours_col:
        comma_hits = dot_hits = 0
        for row in raw_rows[:30]:
            val = row.get(hours_col)
            if val is None:
                continue
            text = str(val).strip()
            if "," in text:
                comma_hits += 1
            elif "." in text:
                dot_hits += 1
        decimal_sep = "," if comma_hits >= dot_hits and comma_hits > 0 else "."
    elif not decimal_sep:
        decimal_sep = "."

    parsed_count = 0
    for idx, row in enumerate(raw_rows):
        heures = (
            _parse_hours(row.get(hours_col), decimal_separator=decimal_sep)
            if hours_col
            else None
        )
        date_parts = (
            _parse_date_value(
                row.get(date_col),
                date_format=opts.get("date_format"),
                default_year=target_year,
                default_month=target_month,
            )
            if date_col
            else None
        )
        entry_raw = row.get(entry_col) if entry_col else None
        exit_raw = None
        if exit_col:
            exit_raw = row.get(exit_col)
            if use_last_exit and not _raw_time_present(exit_raw):
                for col in (exit_2_col, exit_1_col):
                    if col and _raw_time_present(row.get(col)):
                        exit_raw = row.get(col)
                        break

        if punch_pairs_mode:
            if date_parts is None:
                result.warnings.append(f"Ligne {idx + 1} : date illisible.")
                continue
            y, m, d = date_parts
            if m != target_month or y != target_year:
                continue
            if heures is None:
                heures = 0.0
        else:
            if heures is None and date_parts is None:
                continue
            if date_parts is None:
                result.warnings.append(f"Ligne {idx + 1} : date illisible.")
                continue
            y, m, d = date_parts
            if m != target_month or y != target_year:
                continue
            if heures is None:
                heures = 0.0

        mat = str(row.get(mat_col) or "").strip() if mat_col else None
        name_parts = []
        if last_col and row.get(last_col):
            name_parts.append(str(row.get(last_col)).strip())
        if first_col and row.get(first_col):
            name_parts.append(str(row.get(first_col)).strip())
        raw_name = " ".join(name_parts) if name_parts else None
        if not raw_name and full_name_col and row.get(full_name_col):
            raw_name = str(row.get(full_name_col)).strip() or None
        shift_code = (
            str(row.get(shift_col)).strip().upper()
            if shift_col and row.get(shift_col)
            else None
        )

        result.rows.append(
            TabularDayRow(
                matricule=mat or None,
                raw_name=raw_name,
                jour=d,
                month=m,
                year=y,
                heures=heures,
                entry_raw=entry_raw,
                exit_raw=exit_raw,
                shift_code=shift_code,
                raw_payload=dict(row),
            )
        )
        parsed_count += 1

    if parsed_count == 0:
        result.confidence = 0.0
        result.warnings.append("Aucune ligne exploitable pour la période cible.")
    elif parsed_count >= 5:
        result.confidence = 0.95 if punch_pairs_mode else 0.9
    else:
        result.confidence = 0.75 if punch_pairs_mode else 0.65

    return result


def _raw_time_present(raw: Any) -> bool:
    if raw is None:
        return False
    if isinstance(raw, (int, float)):
        return int(raw) > 0
    s = str(raw).strip()
    return bool(s) and s not in ("0", "00", "0000", "-")


__all__ = [
    "TabularDayRow",
    "TabularParseResult",
    "detect_column_mapping",
    "find_header_row_index",
    "is_mapping_sufficient",
    "parse_tabular_file",
    "read_tabular_preview",
    "read_tabular_preview_with_status",
]
