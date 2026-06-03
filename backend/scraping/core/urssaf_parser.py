"""
Parsing générique des tableaux URSSAF (révisions datées, territoires).

Sélectionne le bloc applicable à une date de référence (révision la plus récente
dont la date d'effet est <= aujourd'hui), en privilégiant la métropole.
Gère les tableaux multi-colonnes (ex. janvier–mai | à compter de juin).
"""

from __future__ import annotations

import calendar
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Iterable, Optional

from bs4 import BeautifulSoup, Tag

_YEAR_RE = re.compile(r"\b(20\d{2})\b")

_MONTHS = {
    "janvier": 1,
    "fevrier": 2,
    "février": 2,
    "mars": 3,
    "avril": 4,
    "mai": 5,
    "juin": 6,
    "juillet": 7,
    "aout": 8,
    "août": 8,
    "septembre": 9,
    "octobre": 10,
    "novembre": 11,
    "decembre": 12,
    "décembre": 12,
}

_DATE_PATTERNS = [
    re.compile(
        r"(?:au|à compter du|depuis le|applicable au|en vigueur au|"
        r"à partir du|a partir du)\s+"
        r"(?:le\s+)?1er\s+"
        r"(janvier|fevrier|février|mars|avril|mai|juin|juillet|"
        r"aout|août|septembre|octobre|novembre|decembre|décembre)"
        r"(?:\s+(\d{4}))?",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b1er\s+"
        r"(janvier|fevrier|février|mars|avril|mai|juin|juillet|"
        r"aout|août|septembre|octobre|novembre|decembre|décembre)"
        r"(?:\s+(\d{4}))?",
        re.IGNORECASE,
    ),
]

_DU_AU_PERIOD = re.compile(
    r"du\s+1er\s+(\w+)\s+(\d{4})\s+au\s+31\s+(\w+)(?:\s+(\d{4}))?",
    re.IGNORECASE,
)

_AU_PERIOD = re.compile(
    r"au\s+1er\s+(\w+)\s+(\d{4})",
    re.IGNORECASE,
)


def parse_french_amount(text: str) -> float:
    """Convertit '1 823,03 €' en 1823.03."""
    if not text:
        return 0.0
    cleaned = (
        text.replace("\xa0", "")
        .replace("\u202f", "")
        .replace("\u2009", "")
        .replace(" ", "")
        .strip()
    )
    cleaned = cleaned.replace(",", ".")
    match = re.search(r"\d+\.?\d*", cleaned)
    if match:
        return float(match.group())
    return 0.0


def amounts_in_cells(cells: Iterable[Any], *, min_value: float = 0.0) -> list[float]:
    out: list[float] = []
    for cell in cells:
        val = parse_french_amount(cell.get_text() if hasattr(cell, "get_text") else str(cell))
        if val > min_value:
            out.append(val)
    return out


def first_amount_in_cells(cells: Iterable[Any], *, min_value: float = 0.0) -> Optional[float]:
    vals = amounts_in_cells(cells, min_value=min_value)
    return vals[0] if vals else None


def _normalize_text(text: str) -> str:
    t = unicodedata.normalize("NFD", text.lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def normalize_row_text(text: str) -> str:
    """Normalise le texte d'une ligne de tableau (ordinals, espaces)."""
    t = text.replace("\xa0", " ").replace("\u202f", " ").replace("\u2009", " ")
    t = re.sub(r"\s+", " ", t).strip()
    t = re.sub(r"\b1\s+er\b", "1er", t, flags=re.IGNORECASE)
    return t


def row_text(tr: Tag) -> str:
    return normalize_row_text(tr.get_text(" ", strip=True))


def _month_number(name: str) -> Optional[int]:
    return _MONTHS.get(_normalize_text(name))


def _last_day_of_month(year: int, month: int) -> int:
    return calendar.monthrange(year, month)[1]


def parse_french_effective_date(text: str, *, default_year: int) -> Optional[date]:
    """Extrait une date d'effet depuis une ligne de tableau URSSAF."""
    norm = _normalize_text(normalize_row_text(text))
    for pattern in _DATE_PATTERNS:
        m = pattern.search(norm)
        if not m:
            continue
        month = _month_number(m.group(1))
        if not month:
            continue
        year_raw = m.group(2) if m.lastindex and m.lastindex >= 2 else None
        year = int(year_raw) if year_raw else default_year
        return date(year, month, 1)
    return None


def parse_column_periods(text: str) -> list[tuple[date, Optional[date]]]:
    """
    Extrait les périodes couvertes par les colonnes d'un en-tête URSSAF.
    Ex. « Du 1er janvier 2026 au 31 mai 2026 » + « Au 1er juin 2026 ».
    """
    norm = _normalize_text(normalize_row_text(text))
    periods: list[tuple[date, Optional[date]]] = []

    m = _DU_AU_PERIOD.search(norm)
    if m:
        y_start = int(m.group(2))
        m_start = _month_number(m.group(1))
        m_end = _month_number(m.group(3))
        y_end = int(m.group(4)) if m.lastindex and m.lastindex >= 4 and m.group(4) else y_start
        if m_start and m_end:
            periods.append(
                (
                    date(y_start, m_start, 1),
                    date(y_end, m_end, _last_day_of_month(y_end, m_end)),
                )
            )

    for m in _AU_PERIOD.finditer(norm):
        month = _month_number(m.group(1))
        if not month:
            continue
        start = date(int(m.group(2)), month, 1)
        if not periods or start > periods[-1][0]:
            periods.append((start, None))

    return periods


def pick_amount_for_reference_date(
    amounts: list[float],
    periods: list[tuple[date, Optional[date]]],
    ref: date,
) -> tuple[Optional[float], Optional[date]]:
    """Choisit la valeur de la colonne dont la période couvre ref."""
    if not amounts:
        return None, None
    if not periods:
        return amounts[0], None

    n = min(len(amounts), len(periods))
    for i in range(n):
        start, end = periods[i]
        if ref >= start and (end is None or ref <= end):
            return amounts[i], start

    if periods and ref >= periods[-1][0]:
        return amounts[min(len(amounts), len(periods)) - 1], periods[-1][0]

    return amounts[0], periods[0][0]


def infer_territory_from_amounts(label: str, amounts: list[float]) -> str:
    """Mayotte / COM : seul le cas général horaire est < 10 €."""
    norm = _normalize_text(label)
    is_cas_general = norm == "smic horaire brut"
    if is_cas_general and amounts and max(amounts) < 10.0:
        return "overseas"
    return "mainland"


# --- Territoires explicites ---

_OVERSEAS_MARKERS = (
    "mayotte",
    "polynesie",
    "polynésie",
    "nouvelle-caledonie",
    "nouvelle-calédonie",
    "wallis",
    "futuna",
    "saint-pierre-et-miquelon",
)


def territory_from_text(text: str) -> str:
    norm = _normalize_text(text)
    for marker in _OVERSEAS_MARKERS:
        if marker in norm:
            return "overseas"
    return "mainland"


def is_year_header(text: str) -> Optional[int]:
    stripped = normalize_row_text(text).strip()
    if re.fullmatch(r"20\d{2}", stripped):
        return int(stripped)
    m = _YEAR_RE.search(stripped)
    if m and len(stripped) <= 12:
        return int(m.group(1))
    return None


@dataclass
class UrssafTableSegment:
    year: int
    effective_from: date
    territory: str
    label_values: dict[str, float] = field(default_factory=dict)
    raw_labels: list[str] = field(default_factory=list)

    def set_value(self, label: str, value: float) -> None:
        key = _normalize_label(label)
        if key and value > 0:
            self.label_values[key] = value
            self.raw_labels.append(label)


def _normalize_label(label: str) -> str:
    return _normalize_text(label).strip()


def iter_table_segments(
    rows: Iterable[Tag],
    *,
    default_year: Optional[int] = None,
    reference_date: Optional[date] = None,
) -> list[UrssafTableSegment]:
    ref = reference_date or datetime.now().date()
    ref_year = default_year or ref.year
    segments: list[UrssafTableSegment] = []
    current: Optional[UrssafTableSegment] = None
    last_year = ref_year
    column_periods: list[tuple[date, Optional[date]]] | None = None

    def flush() -> None:
        nonlocal current
        if current and current.label_values:
            segments.append(current)
        current = None

    def open_segment(effective: date, territory: str) -> None:
        nonlocal current, last_year
        if (
            current is not None
            and current.effective_from == effective
            and current.territory == territory
        ):
            return
        flush()
        last_year = effective.year
        current = UrssafTableSegment(
            year=effective.year,
            effective_from=effective,
            territory=territory,
        )

    for tr in rows:
        text = row_text(tr)
        if not text:
            continue

        y = is_year_header(text)
        if y is not None and len(text.strip()) <= 8:
            flush()
            column_periods = None
            last_year = y
            open_segment(date(y, 1, 1), "mainland")
            continue

        header_periods = parse_column_periods(text)
        if header_periods:
            column_periods = header_periods
            if len(header_periods) == 1 and "smic" not in text.lower():
                open_segment(
                    header_periods[0][0],
                    territory_from_text(text),
                )
            continue

        eff = parse_french_effective_date(text, default_year=last_year)
        terr = territory_from_text(text)

        if eff is not None and not header_periods:
            column_periods = [(eff, None)]
            open_segment(eff, terr)
            continue

        if terr == "overseas" and "smic" not in text.lower():
            flush()
            column_periods = None
            continue

        tds = tr.find_all(["td", "th"])
        if len(tds) < 2:
            continue

        label = tds[0].get_text(strip=True)
        amounts = amounts_in_cells(tds[1:])
        if not amounts:
            continue

        if column_periods and len(amounts) > 1:
            val, eff_start = pick_amount_for_reference_date(amounts, column_periods, ref)
            territory = infer_territory_from_amounts(label, amounts)
            if val is None or eff_start is None:
                continue
            open_segment(eff_start, territory)
            current.set_value(label, val)
            continue

        val = amounts[0]
        territory = infer_territory_from_amounts(label, amounts)
        if current is None:
            open_segment(date(last_year, 1, 1), territory)
        elif territory == "overseas" and current.territory == "mainland":
            open_segment(current.effective_from, territory)
        elif territory == "mainland" and current.territory == "overseas":
            open_segment(current.effective_from, territory)
        current.set_value(label, val)

    flush()
    return segments


def iter_segments_from_soup(
    soup: BeautifulSoup,
    **kwargs: Any,
) -> list[UrssafTableSegment]:
    return iter_table_segments(soup.find_all("tr"), **kwargs)


def select_applicable_segment(
    segments: list[UrssafTableSegment],
    *,
    reference_date: Optional[date] = None,
    target_year: Optional[int] = None,
    prefer_mainland: bool = True,
) -> Optional[UrssafTableSegment]:
    ref = reference_date or datetime.now().date()
    year = target_year or ref.year

    candidates = [s for s in segments if s.year == year and s.effective_from <= ref]
    if not candidates:
        candidates = [s for s in segments if s.year == year - 1 and s.effective_from <= ref]
    if not candidates:
        return None

    if prefer_mainland:
        mainland = [s for s in candidates if s.territory == "mainland"]
        if mainland:
            candidates = mainland

    return max(candidates, key=lambda s: (s.effective_from, len(s.label_values)))


def segment_value(segment: UrssafTableSegment, *label_substrings: str) -> Optional[float]:
    keys = [_normalize_text(s) for s in label_substrings]
    for label, val in segment.label_values.items():
        if all(k in label for k in keys):
            return val
    return None


def smic_monthly_hours() -> float:
    return 35.0 * 52.0 / 12.0


def pick_applicable_smic_horaire_from_text(
    text: str,
    *,
    reference_date: Optional[date] = None,
) -> Optional[float]:
    """
    Extrait le SMIC horaire métropole applicable à reference_date depuis un texte libre
    (pages LegiSocial, articles, etc.).
    """
    ref = reference_date or datetime.now().date()
    norm = _normalize_text(normalize_row_text(text))

    if ref.month >= 6:
        june_parts = re.split(rf"au\s+1er\s+juin\s+{ref.year}", norm, maxsplit=1, flags=re.I)
        if len(june_parts) > 1:
            m = re.search(
                r"smic\s+horaire[^\d]*(\d+[,.]\d{2})",
                june_parts[1][:800],
                re.I,
            )
            if m:
                val = parse_french_amount(m.group(1))
                if 10.0 <= val <= 15.0:
                    return val

    if ref.month < 6:
        jan = re.search(
            rf"1er\s+janvier\s+{ref.year}.{{0,400}}?smic\s+horaire[^\d]*(\d+[,.]\d{{2}})",
            norm,
            re.I | re.DOTALL,
        )
        if jan:
            val = parse_french_amount(jan.group(1))
            if 10.0 <= val <= 15.0:
                return val

    candidates: list[float] = []
    for m in re.finditer(r"smic\s+horaire[^\d]*(\d+[,.]\d{2})", norm, re.I):
        val = parse_french_amount(m.group(1))
        if 10.0 <= val <= 15.0:
            candidates.append(val)
    if not candidates:
        return None
    unique = sorted(set(candidates))
    return unique[-1] if ref.month >= 6 else unique[min(1, len(unique) - 1)]
