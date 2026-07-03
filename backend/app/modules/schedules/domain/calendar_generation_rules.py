"""
Règles pures de génération des calendriers prévisionnels — domaine, sans I/O.

Un « modèle horaire » est une semaine type : une liste de configurations jour
(`day_configs`) décrivant, pour chaque jour ISO (1 = lundi … 7 = dimanche) :
type, heures prévues paie, horaires indicatifs, pause et pause payée/non payée.

Un « cycle » est une liste ordonnée de modèles (semaine A, B, … N) permettant
l'alternance de semaines (ex. Lewis, Emilie Vignaud). Le modèle appliqué à une
semaine donnée dépend de la position de son lundi par rapport à une date
d'ancrage (`cycle_anchor`).

Ce module ne dépend d'aucune base : il est entièrement testable unitairement.
"""
from __future__ import annotations

import calendar as _cal
from datetime import date, timedelta
from typing import Any, Callable, Dict, List, Optional, Sequence

# Types de jour considérés comme travaillés (les autres → 0 h).
WORK_TYPES = {"work", "travail"}

# Modes de génération face à un calendrier déjà présent.
OVERWRITE_ALL = "overwrite_all"          # écrase tout
PRESERVE_MANUAL = "preserve_manual"      # conserve les jours modifiés à la main
FILL_EMPTY = "fill_empty"                # ne remplit que les jours vides
OVERWRITE_MODES = {OVERWRITE_ALL, PRESERVE_MANUAL, FILL_EMPTY}

DAY_KEYS_ISO = {
    1: "monday",
    2: "tuesday",
    3: "wednesday",
    4: "thursday",
    5: "friday",
    6: "saturday",
    7: "sunday",
}


def hhmm(hours: int, minutes: int = 0) -> float:
    """Convertit une notation HHhMM (ex. Cartol « 7h50 » = 7 h 50 min) en heures décimales.

    Attention : « 7h50 » signifie 7 h 50 min, PAS 7,50 h. Utilisé uniquement pour
    construire les presets ; l'ambiguïté métier (ex. Lewis « 7,45 ») reste signalée
    par un flag RH, jamais figée ici.
    """
    return round(hours + minutes / 60.0, 4)


def _to_float(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def normalize_day_config(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Complète une entrée `day_configs` avec les champs attendus (rétro-compatible).

    Les anciens modèles ne portent que {day, hours, type} : les champs indicatifs
    (horaires, pause, commentaire) sont simplement optionnels.
    """
    day_type = raw.get("type") or "travail"
    is_work = day_type in WORK_TYPES
    hours = _to_float(raw.get("hours"))
    if hours is None:
        hours = 0.0 if not is_work else 0.0
    return {
        "day": int(raw.get("day") or 0),
        "type": day_type,
        "hours": round(float(hours), 4),
        "start": raw.get("start") or None,
        "end": raw.get("end") or None,
        "break_minutes": int(raw.get("break_minutes") or 0),
        "break_paid": bool(raw.get("break_paid", False)),
        "comment": raw.get("comment") or None,
    }


def week_weekly_hours(day_configs: Sequence[Dict[str, Any]]) -> float:
    """Total hebdomadaire recalculé depuis les jours (source de vérité)."""
    total = 0.0
    for cfg in day_configs:
        norm = normalize_day_config(cfg)
        if norm["type"] in WORK_TYPES:
            total += norm["hours"]
    return round(total, 2)


def day_config_map(day_configs: Sequence[Dict[str, Any]]) -> Dict[int, Dict[str, Any]]:
    """Indexe les jours d'un modèle par jour ISO (1-7)."""
    out: Dict[int, Dict[str, Any]] = {}
    for cfg in day_configs:
        norm = normalize_day_config(cfg)
        if 1 <= norm["day"] <= 7:
            out[norm["day"]] = norm
    return out


def monday_of(d: date) -> date:
    return d - timedelta(days=d.weekday())


def resolve_cycle_week_index(
    cycle_len: int, cycle_anchor: date, monday: date
) -> int:
    """Position (0-based) de la semaine `monday` dans un cycle de `cycle_len` semaines.

    Un cycle d'une seule semaine renvoie toujours 0 (pas d'alternance).
    """
    if cycle_len <= 1:
        return 0
    delta_weeks = (monday_of(monday) - monday_of(cycle_anchor)).days // 7
    return delta_weeks % cycle_len


def is_empty_entry(entry: Optional[Dict[str, Any]]) -> bool:
    """Un jour est « vide » s'il n'existe pas ou n'a aucune heure prévue définie."""
    if not entry:
        return True
    return entry.get("heures_prevues") in (None, "")


def build_month_calendrier_prevu(
    year: int,
    month: int,
    resolve_week_day_map: Callable[[date], Dict[int, Dict[str, Any]]],
    *,
    holidays: Optional[set[int]] = None,
    is_forfait: bool = False,
    existing_entries: Optional[Sequence[Dict[str, Any]]] = None,
    overwrite_mode: str = OVERWRITE_ALL,
    template_id_for_week: Optional[Callable[[date], Optional[str]]] = None,
    day_in_range: Optional[Callable[[date], bool]] = None,
) -> List[Dict[str, Any]]:
    """Construit le `calendrier_prevu` d'un mois (liste d'entrées par jour).

    `resolve_week_day_map(monday)` renvoie la carte jour ISO → config pour la
    semaine du lundi donné (gère l'alternance en amont). Les jours fériés observés
    (`holidays`, numéros de jour du mois) deviennent des jours `ferie` à 0 h. En
    forfait jour, un jour travaillé vaut 1, sinon 0.
    """
    if overwrite_mode not in OVERWRITE_MODES:
        overwrite_mode = OVERWRITE_ALL
    holidays = holidays or set()
    existing_by_day: Dict[int, Dict[str, Any]] = {}
    for e in existing_entries or []:
        try:
            existing_by_day[int(e.get("jour"))] = e
        except (TypeError, ValueError):
            continue

    num_days = _cal.monthrange(year, month)[1]
    out: List[Dict[str, Any]] = []
    for day in range(1, num_days + 1):
        current = date(year, month, day)
        iso = current.isoweekday()
        existing = existing_by_day.get(day)

        # Hors de la période du plan : on ne régénère pas (on préserve l'existant,
        # sinon jour repos neutre pour ne pas écraser d'autres plans).
        if day_in_range is not None and not day_in_range(current):
            if existing:
                out.append(dict(existing))
            else:
                out.append(_make_entry(day, "repos", 0.0, None, is_forfait=False))
            continue

        # Modes de préservation : on garde l'entrée existante sans régénérer.
        if overwrite_mode == PRESERVE_MANUAL and existing and existing.get("manuel"):
            out.append(dict(existing))
            continue
        if overwrite_mode == FILL_EMPTY and not is_empty_entry(existing):
            out.append(dict(existing))
            continue

        monday = monday_of(current)
        day_map = resolve_week_day_map(monday)
        cfg = day_map.get(iso)

        if day in holidays:
            entry = _make_entry(day, "ferie", 0.0, None, is_forfait=False)
        elif cfg is None or cfg["type"] not in WORK_TYPES:
            day_type = cfg["type"] if cfg else "repos"
            entry = _make_entry(day, day_type, 0.0, cfg, is_forfait=False)
        else:
            entry = _make_entry(day, cfg["type"], cfg["hours"], cfg, is_forfait=is_forfait)

        if template_id_for_week is not None:
            entry["source_template_id"] = template_id_for_week(monday)
        entry["manuel"] = False
        out.append(entry)
    return out


def _make_entry(
    day: int,
    day_type: str,
    hours: float,
    cfg: Optional[Dict[str, Any]],
    *,
    is_forfait: bool,
) -> Dict[str, Any]:
    is_work = day_type in WORK_TYPES
    if is_forfait:
        heures_prevues: float = 1.0 if is_work else 0.0
    else:
        heures_prevues = round(float(hours), 4) if is_work else 0.0
    entry: Dict[str, Any] = {
        "jour": day,
        "type": day_type,
        "heures_prevues": heures_prevues,
    }
    if cfg:
        if cfg.get("start"):
            entry["start"] = cfg["start"]
        if cfg.get("end"):
            entry["end"] = cfg["end"]
        if cfg.get("break_minutes"):
            entry["pause_min"] = cfg["break_minutes"]
            entry["pause_payee"] = bool(cfg.get("break_paid", False))
        if cfg.get("comment"):
            entry["commentaire"] = cfg["comment"]
    return entry


def weekly_totals_from_entries(
    entries: Sequence[Dict[str, Any]], year: int, month: int
) -> Dict[str, float]:
    """Totaux par semaine ISO (clé « YYYY-WW ») — pour aperçu RH et tests."""
    totals: Dict[str, float] = {}
    for e in entries:
        try:
            day = int(e.get("jour"))
        except (TypeError, ValueError):
            continue
        iso_year, iso_week, _ = date(year, month, day).isocalendar()
        key = f"{iso_year}-W{iso_week:02d}"
        totals[key] = round(totals.get(key, 0.0) + float(e.get("heures_prevues") or 0.0), 2)
    return totals


__all__ = [
    "WORK_TYPES",
    "OVERWRITE_ALL",
    "PRESERVE_MANUAL",
    "FILL_EMPTY",
    "OVERWRITE_MODES",
    "hhmm",
    "normalize_day_config",
    "week_weekly_hours",
    "day_config_map",
    "monday_of",
    "resolve_cycle_week_index",
    "is_empty_entry",
    "build_month_calendrier_prevu",
    "weekly_totals_from_entries",
]
