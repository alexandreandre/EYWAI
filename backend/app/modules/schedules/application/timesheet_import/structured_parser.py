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
    "entry_2": ("entree 2", "entree2", "entry_2", "entry2"),
    "entry_3": ("entree 3", "entree3", "entry_3", "entry3"),
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
    # Pause visible entre les paires entrée/sortie de la journée (None : une
    # seule paire, la pause n'est pas connue).
    punched_break_minutes: Optional[int] = None
    # Badges de la ligne, dans l'ordre des colonnes : ("E"|"S", minutes).
    punches: List[Tuple[str, int]] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)


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
    skip_period_filter = bool(opts.get("skip_period_filter"))
    # Trois paires entrée/sortie (badgeuse type PMI) : la journée se lit sur
    # toute la séquence des badges, poste de nuit compris.
    colonnes_paires = (
        ("E", entry_col),
        ("S", exit_1_col),
        ("E", mapping.get("entry_2")),
        ("S", exit_2_col),
        ("E", mapping.get("entry_3")),
        ("S", exit_col),
    )
    paires_mode = bool(
        punch_pairs_mode and use_last_exit and mapping.get("entry_2") and exit_1_col
    )

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
            if not skip_period_filter and (m != target_month or y != target_year):
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
            if not skip_period_filter and (m != target_month or y != target_year):
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

        if not _is_plausible_timesheet_row(matricule=mat, raw_name=raw_name, jour=d):
            continue

        shift_code = (
            str(row.get(shift_col)).strip().upper()
            if shift_col and row.get(shift_col)
            else None
        )

        punches: List[Tuple[str, int]] = []
        if paires_mode:
            for kind, col in colonnes_paires:
                minutes = _minutes_badge(row.get(col)) if col else None
                if minutes is not None:
                    punches.append((kind, minutes))

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
                punches=punches,
            )
        )
        parsed_count += 1

    if paires_mode:
        _retraiter_paires(result.rows)

    if parsed_count == 0:
        result.confidence = 0.0
        result.warnings.append("Aucune ligne exploitable pour la période cible.")
    elif parsed_count >= 5:
        result.confidence = 0.95 if punch_pairs_mode else 0.9
    else:
        result.confidence = 0.75 if punch_pairs_mode else 0.65

    return result


def _minutes_badge(raw: Any) -> Optional[int]:
    """800 → 480, « 16:30 » → 990 ; 0, vide ou illisible → None."""
    from app.modules.schedules.domain.punch_accounting_rules import parse_hhmm_value

    if not _raw_time_present(raw):
        return None
    if isinstance(raw, float) and raw.is_integer():
        raw = int(raw)
    return parse_hhmm_value(raw)


def _hhmm(minutes: int) -> int:
    return (minutes // 60) * 100 + minutes % 60


def _libelle(minutes: int) -> str:
    return f"{minutes // 60} h {minutes % 60:02d}"


def _retraiter_paires(rows: List[TabularDayRow]) -> None:
    """Première entrée, dernière sortie, pause entre paires, postes de nuit.

    Un poste de nuit commence sur la ligne du jour (entrée à 20 h, sans
    sortie) et finit sur la ligne du lendemain (sortie à 4 h avant toute
    entrée) : la sortie est rattachée à la veille. Une entrée seule qui
    n'est pas suivie d'une telle sortie reste une entrée sans sortie.
    """
    from datetime import date as _date

    par_salarie: Dict[str, List[TabularDayRow]] = {}
    for r in rows:
        par_salarie.setdefault(r.matricule or r.raw_name or "", []).append(r)

    for lignes in par_salarie.values():
        lignes.sort(key=lambda r: (r.year, r.month, r.jour))
        veille: Optional[TabularDayRow] = None
        entree_en_suspens: Optional[int] = None
        for r in lignes:
            seq = list(r.punches)
            jour = _date(r.year, r.month, r.jour)
            if (
                entree_en_suspens is not None
                and veille is not None
                and (jour - _date(veille.year, veille.month, veille.jour)).days == 1
                and seq
                and seq[0][0] == "S"
            ):
                sortie = seq.pop(0)[1]
                if veille.exit_raw is not None:
                    # La veille a déjà son poste de jour : deux postes le même
                    # jour ne tiennent pas dans une entrée et une sortie.
                    veille.notes.append(
                        f"Deuxième poste {_libelle(entree_en_suspens)} → "
                        f"{_libelle(sortie)} non compté : à saisir à la main."
                    )
                else:
                    veille.entry_raw = _hhmm(entree_en_suspens)
                    veille.exit_raw = _hhmm(sortie)
                    veille.punched_break_minutes = None
                r.notes.append(
                    f"Sortie à {_libelle(sortie)} rattachée au poste de nuit de la veille."
                )
            entree_en_suspens = None

            premiere_entree = next((i for i, p in enumerate(seq) if p[0] == "E"), None)
            derniere_sortie = max(
                (i for i, p in enumerate(seq) if p[0] == "S"
                 and premiere_entree is not None and i > premiere_entree),
                default=None,
            )
            if premiere_entree is None:
                r.entry_raw = None
                r.exit_raw = _hhmm(seq[0][1]) if seq else None
            elif derniere_sortie is None:
                r.entry_raw = _hhmm(seq[premiere_entree][1])
                r.exit_raw = None
                entree_en_suspens = seq[premiere_entree][1]
            else:
                poste = seq[premiere_entree : derniere_sortie + 1]
                r.entry_raw = _hhmm(poste[0][1])
                r.exit_raw = _hhmm(poste[-1][1])
                pauses = [
                    poste[i + 1][1] - poste[i][1]
                    for i in range(len(poste) - 1)
                    if poste[i][0] == "S" and poste[i + 1][0] == "E"
                ]
                r.punched_break_minutes = (
                    sum(max(0, p) for p in pauses) if pauses else None
                )
                suite = seq[derniere_sortie + 1 :]
                if suite and suite[-1][0] == "E":
                    entree_en_suspens = suite[-1][1]
                    r.notes.append(
                        f"Entrée à {_libelle(suite[-1][1])} sans sortie ce jour-là."
                    )
            veille = r


def _raw_time_present(raw: Any) -> bool:
    if raw is None:
        return False
    if isinstance(raw, (int, float)):
        return int(raw) > 0
    s = str(raw).strip()
    return bool(s) and s not in ("0", "00", "0000", "-")


def _is_plausible_timesheet_row(
    *,
    matricule: Optional[str],
    raw_name: Optional[str],
    jour: int,
) -> bool:
    if jour < 1 or jour > 31:
        return False
    mat = (matricule or "").strip()
    name = (raw_name or "").strip()
    if mat in ("0", "") and not name:
        return False
    if name.startswith("=") or name.lower().startswith("intérimaire n°"):
        return True
    if mat in ("0", "") and name.lower() in ("", "========================================"):
        return False
    return bool(mat or name)


def filter_tabular_rows_to_period(
    rows: List[TabularDayRow],
    *,
    start: Optional[date],
    end: Optional[date],
    eff_year: int,
    eff_month: int,
) -> List[TabularDayRow]:
    """Conserve les lignes dans la période détectée et le mois effectif."""
    if not rows:
        return []
    filtered: List[TabularDayRow] = []
    for row in rows:
        row_date = date(row.year, row.month, row.jour)
        if start and end and (row_date < start or row_date > end):
            continue
        if row.year != eff_year or row.month != eff_month:
            continue
        filtered.append(row)
    return filtered


__all__ = [
    "TabularDayRow",
    "TabularParseResult",
    "detect_column_mapping",
    "filter_tabular_rows_to_period",
    "find_header_row_index",
    "is_mapping_sufficient",
    "parse_tabular_file",
    "read_tabular_preview",
    "read_tabular_preview_with_status",
]
