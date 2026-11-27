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

# Colonne sans en-tête : gardée sous un nom technique (« _col_13 » = 13e
# colonne) pour que la colonne des heures retenues par le client, souvent sans
# titre, reste lisible. Jamais proposée comme en-tête ni reconnue par alias.
COLONNE_SANS_TITRE = "_col_"


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
    # Heures retenues par le client dans son fichier (colonne à côté des
    # heures pointées) : quand elles sont remplies, `heures` les prend et le
    # calcul des badges ne réécrit pas le jour.
    heures_retenues: Optional[float] = None
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


# Heures décidées par l'entreprise à côté des heures pointées : elles font foi.
# Titre exact seulement (une fois normalisé) : « Total heures semaine »,
# « … nuit », « … théoriques », « … sup » ne sont jamais la colonne retenue.
TITRES_HEURES_RETENUES = ("heures retenues", "heures payees")
# « Total heures » n'est retenu qu'à côté d'un total POINTÉ (« Tot H Poin ») :
# à côté d'« Heures normales » et « Heures sup », c'est leur somme.
TITRE_TOTAL_HEURES = "total heures"


def _heures_supplementaires(header: str) -> bool:
    return re.search(r"\bsup", _normalize_header(header)) is not None


def _total_pointe(header: str) -> bool:
    norm = _normalize_header(header)
    return "poin" in norm or "badg" in norm


def _colonne_retenue_titree(headers: List[str], hours_col: Optional[str]) -> Optional[str]:
    if not hours_col:
        return None
    for header in headers:
        if not header or header == hours_col or header.startswith(COLONNE_SANS_TITRE):
            continue
        norm = _normalize_header(header)
        if norm in TITRES_HEURES_RETENUES:
            return header
        if norm == TITRE_TOTAL_HEURES and _total_pointe(hours_col):
            return header
    return None


def detect_column_mapping(headers: List[str]) -> Dict[str, str]:
    mapping: Dict[str, str] = {}
    # « Heures retenues » / « Heures payées » ne prennent pas la place des
    # heures pointées ; seules, elles restent la colonne des heures.
    differees = [
        h for h in headers if h and _normalize_header(h) in TITRES_HEURES_RETENUES
    ]
    for header in [h for h in headers if h not in differees] + differees:
        if not header or header.startswith(COLONNE_SANS_TITRE):
            continue
        for field_name, aliases in DEFAULT_COLUMN_ALIASES.items():
            if field_name in mapping:
                continue
            if field_name == "hours" and _heures_supplementaires(header):
                # « Heures sup » n'est jamais la colonne des heures du jour.
                continue
            if _match_alias(header, aliases):
                mapping[field_name] = header
                break
    retenue = _colonne_retenue_titree(headers, mapping.get("hours"))
    if not retenue and mapping.get("hours") and (
        _normalize_header(mapping["hours"]) in TITRES_HEURES_RETENUES
    ):
        # « Heures payées » seule : elle fait foi, un jour vide reste vide.
        retenue = mapping["hours"]
    if retenue:
        mapping["hours_retained"] = retenue
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
    if not any(header_cells):
        return [], []
    # Les colonnes sans en-tête sont gardées sous un nom technique (la colonne
    # des heures retenues n'a souvent pas de titre) ; les en-têtes rendus
    # restent les seuls titrés.
    header_pairs = [
        (i, name or f"{COLONNE_SANS_TITRE}{i + 1}") for i, name in enumerate(header_cells)
    ]
    headers = [name for name in header_cells if name]
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
    rows = _sauter_lignes(rows, headers, skip_rows)
    rows = [
        {k: v for k, v in r.items() if not k.startswith(COLONNE_SANS_TITRE)}
        for r in rows
        if not _sans_colonne_titree(r, headers)
    ]
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

    raw_rows = _sauter_lignes(raw_rows, headers, skip_rows)

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
    if not punch_pairs_mode and not hours_col:
        sup = [h for h in headers if h and _heures_supplementaires(h)]
        if sup:
            # Ni heures du jour ni badges : jamais 0 h partout, un refus lisible.
            from app.modules.schedules.application.exceptions import ScheduleAppError

            raise ScheduleAppError(
                "validation",
                "Colonne des heures du jour introuvable : seulement "
                + ", ".join(f"« {h} »" for h in sup)
                + ".",
                status_code=422,
            )
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

    identity_cols = [c for c in (mat_col, last_col, first_col, full_name_col) if c]
    badge_cols = [c for _, c in colonnes_paires if c]

    decimal_sep = str(opts.get("decimal_separator") or "")
    if not decimal_sep and hours_col:
        decimal_sep = _separateur_decimal(raw_rows, hours_col)
    elif not decimal_sep:
        decimal_sep = "."

    # Heures retenues par l'entreprise : colonne au titre exact, sinon
    # retrouvée par sa place, ses valeurs et les lignes de total.
    retained_col = mapping.get("hours_retained")
    if not retained_col and column_mapping:
        # Mapping enregistré avant la colonne retenue : son titre la désigne.
        retained_col = _colonne_retenue_titree(headers, hours_col)
        if retained_col:
            mapping = {**mapping, "hours_retained": retained_col}
            result.column_mapping = mapping
    if not retained_col and hours_col:
        retained_col, alerte = _detecter_colonne_retenue(
            raw_rows,
            hours_col=hours_col,
            date_col=date_col,
            identity_cols=identity_cols,
            badge_cols=badge_cols,
        )
        if retained_col:
            mapping = {**mapping, "hours_retained": retained_col}
            result.column_mapping = mapping
        if alerte:
            result.warnings.append(alerte)
    retained_sep = (
        str(opts.get("decimal_separator") or "") or _separateur_decimal(raw_rows, retained_col)
        if retained_col
        else "."
    )

    parsed_count = 0
    numero = 0  # numéro de ligne tel qu'avant ce lot (lignes titrées seules)
    for row in raw_rows:
        if _sans_colonne_titree(row, headers):
            # Ligne de total d'un salarié (rien que la colonne retenue, sans
            # titre) : ce n'est pas un jour.
            continue
        numero += 1
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
                if _ligne_de_total(
                    row, date_col=date_col, identity_cols=identity_cols, badge_cols=badge_cols
                ):
                    continue
                result.warnings.append(f"Ligne {numero} : date illisible.")
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
                if _ligne_de_total(
                    row, date_col=date_col, identity_cols=identity_cols, badge_cols=badge_cols
                ):
                    continue
                result.warnings.append(f"Ligne {numero} : date illisible.")
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

        heures_retenues: Optional[float] = None
        notes: List[str] = []
        if retained_col:
            heures_retenues = _parse_hours(
                row.get(retained_col), decimal_separator=retained_sep
            )
            if heures_retenues is not None:
                heures = heures_retenues
            elif (
                punches
                or _raw_time_present(entry_raw)
                or _raw_time_present(exit_raw)
            ):
                notes.append(
                    "Heures retenues vides dans le fichier : heures calculées "
                    "depuis les badges, à vérifier."
                )
            elif retained_col == hours_col:
                # Seule colonne d'heures, titrée « Heures payées » : vide, le
                # jour reste vide (à compléter), jamais 0 h.
                heures = None
                notes.append(
                    f"« {retained_col} » vide dans le fichier : jour à compléter."
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
                heures_retenues=heures_retenues,
                raw_payload=dict(row),
                punches=punches,
                notes=notes,
            )
        )
        parsed_count += 1

    if paires_mode:
        _retraiter_paires(result.rows)

    if retained_col and any(r.heures_retenues is not None for r in result.rows):
        # Jamais d'état silencieux : l'écran dit d'où viennent les heures.
        position = list(raw_rows[0].keys()).index(retained_col) + 1 if raw_rows else 0
        titre = (
            "sans titre"
            if retained_col.startswith(COLONNE_SANS_TITRE)
            else f"« {retained_col} »"
        )
        result.warnings.append(
            f"Heures lues dans la colonne {titre} ({position}e colonne) : retenues "
            "par l'entreprise, elles remplacent le calcul des badges ; aucune revue "
            "d'heures en plus sur ces jours."
        )

    if parsed_count == 0:
        result.confidence = 0.0
        result.warnings.append("Aucune ligne exploitable pour la période cible.")
    elif parsed_count >= 5:
        result.confidence = 0.95 if punch_pairs_mode else 0.9
    else:
        result.confidence = 0.75 if punch_pairs_mode else 0.65

    return result


def _sans_colonne_titree(row: Dict[str, Any], headers: List[str]) -> bool:
    """Vrai quand seules des colonnes sans titre sont remplies (ligne de total
    du fichier) : une telle ligne n'existait pas avant qu'on les garde."""
    return not any(_cell_str(row.get(h)) for h in headers)


def _separateur_decimal(raw_rows: List[Dict[str, Any]], col: Optional[str]) -> str:
    comma_hits = dot_hits = 0
    for row in raw_rows[:30]:
        val = row.get(col) if col else None
        if val is None:
            continue
        text = str(val).strip()
        if "," in text:
            comma_hits += 1
        elif "." in text:
            dot_hits += 1
    return "," if comma_hits >= dot_hits and comma_hits > 0 else "."


def _nombre(raw: Any) -> Optional[float]:
    if raw is None or isinstance(raw, bool):
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    text = str(raw).strip().replace(" ", "").replace(",", ".")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _est_colonne_commentaire(header: str) -> bool:
    norm = _normalize_header(header)
    return any(m in norm for m in ("comment", "observation", "remarque", "motif"))


def _ligne_de_total(
    row: Dict[str, Any],
    *,
    date_col: Optional[str],
    identity_cols: List[str],
    badge_cols: List[str],
) -> bool:
    """Sans date, sans salarié et sans aucun badge : la ligne qui clôt les
    jours d'un salarié. Une ligne de suite avec des badges n'en est pas une."""
    if date_col and _cell_str(row.get(date_col)):
        return False
    if any(_cell_str(row.get(c)) for c in identity_cols):
        return False
    return not any(_raw_time_present(row.get(c)) for c in badge_cols)


def _sauter_lignes(
    rows: List[Dict[str, Any]], headers: List[str], n: int
) -> List[Dict[str, Any]]:
    """`skip_rows` compte les lignes comme avant ce lot : les lignes où seules
    des colonnes sans titre sont remplies ne comptent pas."""
    if n <= 0:
        return rows
    vues = 0
    for i, row in enumerate(rows):
        if not _sans_colonne_titree(row, headers):
            vues += 1
            if vues == n:
                return rows[i + 1 :]
    return []


# Lignes de total : au moins deux, et la majorité, doivent valoir la somme des
# jours qui les précèdent. Chez le client du 27/11, certaines portent l'horaire
# du contrat (35, 28…) plutôt que la somme : la majorité suffit.
MIN_TOTAUX_CONCORDANTS = 2
# Proche des heures pointées : sur les jours badgés, au moins 70 % à 1,5 h près.
ECART_MAX_AU_POINTE = 1.5
PART_MIN_PROCHE_DU_POINTE = 0.7
# Cellules texte (« CP », « abs ») : vides, tant qu'elles restent rares.
PART_MIN_NUMERIQUE = 0.8


def _totaux_concordent(
    raw_rows: List[Dict[str, Any]],
    col: str,
    *,
    date_col: Optional[str],
    identity_cols: List[str],
    badge_cols: List[str],
) -> bool:
    accord = desaccord = 0
    somme = 0.0
    for row in raw_rows:
        if date_col and _cell_str(row.get(date_col)):
            somme += _nombre(row.get(col)) or 0.0
            continue
        if not _ligne_de_total(
            row, date_col=date_col, identity_cols=identity_cols, badge_cols=badge_cols
        ):
            continue
        total = _nombre(row.get(col))
        if total is None:
            continue
        if abs(total - somme) <= 0.011:
            accord += 1
        else:
            desaccord += 1
        somme = 0.0
    return accord >= MIN_TOTAUX_CONCORDANTS and accord > desaccord


def _detecter_colonne_retenue(
    raw_rows: List[Dict[str, Any]],
    *,
    hours_col: str,
    date_col: Optional[str],
    identity_cols: List[str],
    badge_cols: List[str],
) -> Tuple[Optional[str], Optional[str]]:
    """Colonne des heures retenues sans en-tête : (colonne, alerte).

    Jamais par sa lettre (une colonne en plus décale tout). Une colonne sans
    titre, après les heures pointées et avant les commentaires, est retenue
    si ses valeurs sont des heures plausibles (0 à 24 h, pas que des 0 et des
    1, pas une seule valeur partout), proches des heures pointées (70 % des
    jours badgés à 1,5 h près), confirmées par les lignes de total, et
    numériques à 80 % au moins.

    Une candidate rejetée sans ambiguïté (paniers, horaire théorique, numéro
    de semaine, relevé sans badges) ne dit rien ; une candidate qui ressemble
    aux heures retenues mais échoue sur les totaux ou le texte le dit.
    """
    if not raw_rows or not date_col or not badge_cols:
        return None, None
    ordre = list(raw_rows[0].keys())
    if hours_col not in ordre:
        return None, None
    debut = ordre.index(hours_col) + 1
    fin = next(
        (i for i in range(debut, len(ordre)) if _est_colonne_commentaire(ordre[i])),
        len(ordre),
    )
    jours = [r for r in raw_rows if _cell_str(r.get(date_col))]

    retenues: List[str] = []
    alertes: List[str] = []
    for col in ordre[debut:fin]:
        if not col.startswith(COLONNE_SANS_TITRE):
            continue
        remplies = [r.get(col) for r in jours if _cell_str(r.get(col))]
        valeurs = [v for v in (_nombre(x) for x in remplies) if v is not None]
        if not valeurs:
            continue
        distinctes = set(valeurs)
        if (
            any(v < 0 or v > 24 for v in valeurs)
            or distinctes <= {0.0, 1.0}
            or len(distinctes) == 1
        ):
            continue
        ecarts = [
            abs(v - h)
            for r in jours
            if any(_raw_time_present(r.get(c)) for c in badge_cols)
            and (v := _nombre(r.get(col))) is not None
            and (h := _nombre(r.get(hours_col))) is not None
        ]
        if not ecarts or (
            sum(1 for e in ecarts if e <= ECART_MAX_AU_POINTE) / len(ecarts)
            < PART_MIN_PROCHE_DU_POINTE
        ):
            continue
        position = ordre.index(col) + 1
        if not _totaux_concordent(
            raw_rows, col, date_col=date_col, identity_cols=identity_cols, badge_cols=badge_cols
        ):
            alertes.append(
                f"La colonne sans titre ({position}e colonne) après « {hours_col} » "
                "ressemble à des heures retenues, mais ses lignes de total ne "
                "concordent pas : heures calculées depuis les badges, à vérifier."
            )
            continue
        if len(valeurs) / len(remplies) < PART_MIN_NUMERIQUE:
            alertes.append(
                f"La colonne sans titre ({position}e colonne) après « {hours_col} » "
                f"contient trop de texte ({len(remplies) - len(valeurs)} cellules sur "
                f"{len(remplies)}) pour y lire les heures retenues : heures calculées "
                "depuis les badges, à vérifier."
            )
            continue
        retenues.append(col)

    if len(retenues) == 1:
        return retenues[0], None
    if len(retenues) > 1:
        return None, (
            f"Plusieurs colonnes sans titre après « {hours_col} » ressemblent à des "
            "heures retenues : heures calculées depuis les badges, à vérifier."
        )
    return None, (alertes[0] if alertes else None)


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
