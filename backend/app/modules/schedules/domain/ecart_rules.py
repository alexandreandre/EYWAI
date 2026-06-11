"""
Règles partagées de calcul d'écart planifié / réel (calendrier paie).
Utilisées par analytics gestion et la revue pré-paie.
"""

from __future__ import annotations

import calendar
from datetime import date, datetime
from typing import Any, Dict, List, Set

ECART_THRESHOLD_HOURS = 2.0
ECART_THRESHOLD_RATIO = 0.1

EmployeeRowStatus = str  # a_saisir | saisi | saisi_avec_ecart


def parse_iso_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    raw = str(value)[:10]
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def is_forfait_jour(statut: str | None) -> bool:
    if not statut:
        return False
    s = str(statut).lower().replace(" ", "_")
    return "forfait" in s and "jour" in s


def sum_hours(values: List[Any]) -> float:
    total = 0.0
    for v in values:
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            total += float(v)
    return total


def compute_month_completion(
    planned_days: List[Dict[str, Any]], year: int, month: int
) -> str:
    days_in_month = calendar.monthrange(year, month)[1]
    by_jour = {int(d.get("jour", 0)): d for d in planned_days if d.get("jour")}
    for day in range(1, days_in_month + 1):
        dt = date(year, month, day)
        if dt.weekday() >= 5:
            continue
        row = by_jour.get(day)
        if row is None:
            return "a_saisir"
        hp = row.get("heures_prevues")
        if hp is None:
            return "a_saisir"
    return "saisi"


def is_significant_ecart(heures_prevues: float, heures_faites: float) -> bool:
    ecart = abs(heures_faites - heures_prevues)
    if ecart <= ECART_THRESHOLD_HOURS:
        return False
    if heures_prevues <= 0:
        return ecart > ECART_THRESHOLD_HOURS
    return ecart / heures_prevues > ECART_THRESHOLD_RATIO


def compute_row_status(
    planned_days: List[Dict[str, Any]],
    actual_days: List[Dict[str, Any]],
    year: int,
    month: int,
    forfait: bool,
) -> EmployeeRowStatus:
    completion = compute_month_completion(planned_days, year, month)
    if completion == "a_saisir":
        return "a_saisir"
    heures_prevues = sum_hours([d.get("heures_prevues") for d in planned_days])
    heures_faites = sum_hours([d.get("heures_faites") for d in actual_days])
    if forfait:
        jours_prevus = sum(
            1
            for d in planned_days
            if d.get("type") == "travail" and d.get("heures_prevues") == 1
        )
        jours_faits = sum(1 for d in actual_days if d.get("heures_faites") == 1)
        return "saisi_avec_ecart" if jours_faits != jours_prevus else "saisi"
    if is_significant_ecart(heures_prevues, heures_faites):
        return "saisi_avec_ecart"
    return "saisi"


def month_period_bounds(year: int, month: int) -> tuple[date, date]:
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last_day)


def validated_absence_days_in_month(
    absences: List[Dict[str, Any]], year: int, month: int
) -> Set[int]:
    days: Set[int] = set()
    start, end = month_period_bounds(year, month)
    for req in absences:
        selected = req.get("selected_days")
        if not isinstance(selected, list):
            continue
        for raw in selected:
            d = parse_iso_date(raw)
            if d and start <= d <= end:
                days.add(d.day)
    return days


def detect_absence_conflicts(
    planned_days: List[Dict[str, Any]], validated_days: Set[int]
) -> int:
    conflicts = 0
    by_jour = {int(d.get("jour", 0)): d for d in planned_days if d.get("jour")}
    for day in validated_days:
        row = by_jour.get(day)
        if not row:
            conflicts += 1
            continue
        t = str(row.get("type") or "")
        if t not in ("arret_maladie", "conge"):
            conflicts += 1
    return conflicts


def detect_absence_conflict_days(
    planned_days: List[Dict[str, Any]], validated_days: Set[int]
) -> List[int]:
    """Retourne la liste des jours en conflit (absence validée vs calendrier)."""
    conflict_days: List[int] = []
    by_jour = {int(d.get("jour", 0)): d for d in planned_days if d.get("jour")}
    for day in sorted(validated_days):
        row = by_jour.get(day)
        if not row:
            conflict_days.append(day)
            continue
        t = str(row.get("type") or "")
        if t not in ("arret_maladie", "conge"):
            conflict_days.append(day)
    return conflict_days


def compute_day_ecarts(
    planned_days: List[Dict[str, Any]],
    actual_days: List[Dict[str, Any]],
    *,
    forfait: bool,
) -> List[Dict[str, Any]]:
    """Détail jour par jour des écarts significatifs."""
    planned_by_jour = {int(d.get("jour", 0)): d for d in planned_days if d.get("jour")}
    actual_by_jour = {int(d.get("jour", 0)): d for d in actual_days if d.get("jour")}
    details: List[Dict[str, Any]] = []

    for jour, planned in sorted(planned_by_jour.items()):
        if str(planned.get("type") or "") != "travail":
            continue
        actual = actual_by_jour.get(jour, {})
        if forfait:
            prev = 1 if planned.get("heures_prevues") == 1 else 0
            fait = 1 if actual.get("heures_faites") == 1 else 0
            ecart = fait - prev
            if ecart == 0:
                continue
            details.append(
                {
                    "jour": jour,
                    "heures_prevues": float(prev),
                    "heures_faites": float(fait),
                    "ecart": float(ecart),
                    "heures_sup": False,
                }
            )
            continue

        prev_raw = planned.get("heures_prevues")
        fait_raw = actual.get("heures_faites")
        prev = float(prev_raw) if isinstance(prev_raw, (int, float)) else 0.0
        fait = float(fait_raw) if isinstance(fait_raw, (int, float)) else 0.0
        ecart = fait - prev
        if abs(ecart) < 0.01:
            continue
        details.append(
            {
                "jour": jour,
                "heures_prevues": prev,
                "heures_faites": fait,
                "ecart": ecart,
                "heures_sup": ecart > 0 and fait > prev,
            }
        )
    return details


def compute_heures_supplementaires(
    planned_days: List[Dict[str, Any]],
    actual_days: List[Dict[str, Any]],
) -> float:
    """Total heures sup (réel > prévu sur jours travail, hors forfait)."""
    planned_by_jour = {int(d.get("jour", 0)): d for d in planned_days if d.get("jour")}
    actual_by_jour = {int(d.get("jour", 0)): d for d in actual_days if d.get("jour")}
    total = 0.0
    for jour, planned in planned_by_jour.items():
        if str(planned.get("type") or "") != "travail":
            continue
        prev_raw = planned.get("heures_prevues")
        actual = actual_by_jour.get(jour, {})
        fait_raw = actual.get("heures_faites")
        prev = float(prev_raw) if isinstance(prev_raw, (int, float)) else 0.0
        fait = float(fait_raw) if isinstance(fait_raw, (int, float)) else 0.0
        if fait > prev:
            total += fait - prev
    return total
