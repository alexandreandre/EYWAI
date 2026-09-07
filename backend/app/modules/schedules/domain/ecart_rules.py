"""
Règles partagées de calcul d'écart planifié / réel (calendrier paie).
Utilisées par analytics gestion et la revue pré-paie.
"""

from __future__ import annotations

import calendar
from datetime import date, datetime
from typing import Any, Dict, List, Set

from app.shared.domain.absence_calendar import ABSENCE_CALENDAR_TYPES

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


def is_day_ready_for_payroll(
    planned: Dict[str, Any] | None,
    actual: Dict[str, Any] | None,
    *,
    forfait: bool = False,
) -> bool:
    """Jour prêt pour la paie : travail exige prévu + réel ; les autres types sont complets."""
    if not planned:
        return False
    day_type = str(planned.get("type") or "")
    if day_type == "travail":
        prev = planned.get("heures_prevues")
        if prev is None:
            return False
        if not actual or actual.get("heures_faites") is None:
            return False
        # Horaire : 0 h sur un jour prévu = pas encore saisi (distinct du forfait 0/1).
        if not forfait and float(prev) > 0 and float(actual.get("heures_faites") or 0) <= 0:
            return False
        return True
    return True


def compute_month_completion(
    planned_days: List[Dict[str, Any]],
    actual_days: List[Dict[str, Any]],
    year: int,
    month: int,
    *,
    forfait: bool = False,
) -> str:
    days_in_month = calendar.monthrange(year, month)[1]
    planned_by_jour = {
        int(d.get("jour", 0)): d for d in planned_days if d.get("jour")
    }
    actual_by_jour = {
        int(d.get("jour", 0)): d for d in actual_days if d.get("jour")
    }
    for day in range(1, days_in_month + 1):
        if not is_day_ready_for_payroll(
            planned_by_jour.get(day),
            actual_by_jour.get(day),
            forfait=forfait,
        ):
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
    completion = compute_month_completion(
        planned_days, actual_days, year, month, forfait=forfait
    )
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


# Types de demande qui n'écrivent JAMAIS le calendrier (par design,
# cf. shared/domain/absence_calendar.ABSENCE_TYPE_TO_CALENDAR_TYPE) : une
# demande validée de ces types n'est pas un conflit de calendrier.
_TYPES_DEMANDE_SANS_CALENDRIER = frozenset({"jtc", "sans_solde"})

# Types de jour qui reflètent correctement une absence validée : la source
# partagée ABSENCE_CALENDAR_TYPES (conge, conges_payes, rtt, arret_maladie)
# + ferie (un férié couvert par une demande n'est jamais retypé). Miroir de
# la détection frontend (src/lib/schedulesAbsenceConflict.ts) — l'ancienne
# liste locale ("arret_maladie", "conge") déclarait en conflit chaque CP ou
# RTT correctement projeté (retour Gaëlle 07/09, dossier GIRERD).
_TYPES_JOUR_SANS_CONFLIT = frozenset(ABSENCE_CALENDAR_TYPES | {"ferie"})


def validated_absence_days_in_month(
    absences: List[Dict[str, Any]], year: int, month: int
) -> Set[int]:
    days: Set[int] = set()
    start, end = month_period_bounds(year, month)
    for req in absences:
        if str(req.get("type") or "") in _TYPES_DEMANDE_SANS_CALENDRIER:
            continue
        selected = req.get("selected_days")
        if not isinstance(selected, list):
            continue
        for raw in selected:
            d = parse_iso_date(raw)
            if d and start <= d <= end:
                days.add(d.day)
    return days


def _jour_en_conflit(
    row: Dict[str, Any] | None, day: int, year: int, month: int
) -> bool:
    """Un jour d'absence validée est en conflit si le calendrier le contredit.

    Exemptions (mêmes règles que le frontend) : les types d'absence projetés
    et `ferie` ; `repos` toujours ; `weekend` (ou ligne absente) un samedi ou
    un dimanche — un arrêt calendaire couvre les week-ends sans les retyper.
    """
    try:
        est_weekend = date(year, month, day).weekday() >= 5
    except ValueError:
        est_weekend = False
    if not row:
        return not est_weekend
    t = str(row.get("type") or "")
    if t in _TYPES_JOUR_SANS_CONFLIT:
        return False
    if t == "repos":
        return False
    if t == "weekend" and est_weekend:
        return False
    return True


def detect_absence_conflicts(
    planned_days: List[Dict[str, Any]],
    validated_days: Set[int],
    year: int,
    month: int,
) -> int:
    return len(detect_absence_conflict_days(planned_days, validated_days, year, month))


def detect_absence_conflict_days(
    planned_days: List[Dict[str, Any]],
    validated_days: Set[int],
    year: int,
    month: int,
) -> List[int]:
    """Retourne la liste des jours en conflit (absence validée vs calendrier)."""
    by_jour = {int(d.get("jour", 0)): d for d in planned_days if d.get("jour")}
    return [
        day
        for day in sorted(validated_days)
        if _jour_en_conflit(by_jour.get(day), day, year, month)
    ]


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
