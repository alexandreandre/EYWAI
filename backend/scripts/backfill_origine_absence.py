#!/usr/bin/env python3
"""Pose le marqueur `origine="absence"` sur les jours d'absence déjà validés.

Depuis le lot « préservation du planning », la validation d'une absence écrit
`origine="absence"` sur chaque jour du `planned_calendar`, et la régénération
d'un planning refuse d'écraser un jour ainsi marqué (voir
`schedules.domain.calendar_generation_rules.build_month_calendrier_prevu`).

Les absences validées AVANT ce lot n'ont pas le marqueur : elles restent donc
balayables par une régénération. Ce script rapproche les demandes d'absence
validées (`absence_requests.status = "validated"`) et les plannings
(`employee_schedules.planned_calendar`) pour poser le marqueur manquant.

Règles :
- seuls les jours listés dans `selected_days` d'une demande validée sont
  considérés ;
- le jour n'est marqué que si son type de calendrier est un type d'absence
  (cf. `ABSENCE_CALENDAR_TYPES`, aligné sur le mapping de
  `absences.infrastructure.providers.CalendarUpdateProvider`) ;
- `type` et `heures_prevues` ne sont JAMAIS modifiés ;
- un jour portant déjà une clé `origine` est laissé tel quel : le script est
  idempotent et rejouable.

Sans `--apply`, rien n'est écrit : le compte rendu de simulation est affiché.

Usage :
    venv/bin/python -m scripts.backfill_origine_absence
    venv/bin/python -m scripts.backfill_origine_absence --company "Colorplast"
    venv/bin/python -m scripts.backfill_origine_absence --apply
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

# Types de calendrier produits par une validation d'absence.
# Source : absences.infrastructure.providers.CalendarUpdateProvider
# (`type_mapping` + le cas arrêt de travail).
ABSENCE_CALENDAR_TYPES = frozenset(
    {"arret_maladie", "conge", "conges_payes", "rtt"}
)

ORIGINE_ABSENCE = "absence"


def _as_date(raw: Any) -> Optional[date]:
    """Convertit une entrée de `selected_days` (str ISO ou date) en date."""
    if raw is None or raw == "":
        return None
    if isinstance(raw, date) and not isinstance(raw, datetime):
        return raw
    if isinstance(raw, datetime):
        return raw.date()
    try:
        return date.fromisoformat(str(raw)[:10])
    except (TypeError, ValueError):
        return None


def days_by_employee_month(
    absence_rows: List[Dict[str, Any]],
) -> Dict[Tuple[str, int, int], Set[int]]:
    """Regroupe les jours des demandes validées par (employé, année, mois)."""
    grouped: Dict[Tuple[str, int, int], Set[int]] = defaultdict(set)
    for row in absence_rows:
        employee_id = row.get("employee_id")
        if not employee_id:
            continue
        for raw_day in row.get("selected_days") or []:
            jour = _as_date(raw_day)
            if jour is None:
                continue
            grouped[(str(employee_id), jour.year, jour.month)].add(jour.day)
    return grouped


def mark_entries(
    calendrier_prevu: List[Dict[str, Any]], jours: Set[int]
) -> Tuple[List[Dict[str, Any]], List[int]]:
    """Retourne (calendrier marqué, jours effectivement marqués).

    Fonction pure : aucune I/O, testable seule. `type` et `heures_prevues`
    restent intacts ; seuls les jours d'absence sans clé `origine` sont
    complétés.
    """
    marques: List[int] = []
    sortie: List[Dict[str, Any]] = []
    for entree in calendrier_prevu:
        nouvelle = dict(entree)
        try:
            jour = int(nouvelle.get("jour"))
        except (TypeError, ValueError):
            sortie.append(nouvelle)
            continue
        if (
            jour in jours
            and nouvelle.get("type") in ABSENCE_CALENDAR_TYPES
            and "origine" not in nouvelle
        ):
            nouvelle["origine"] = ORIGINE_ABSENCE
            marques.append(jour)
        sortie.append(nouvelle)
    return sortie, marques


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--apply", action="store_true", help="Écrire en base (sinon simulation)."
    )
    parser.add_argument("--company", help="Limiter à une société (nom exact).")
    args = parser.parse_args(argv)

    from app.core.database import supabase, supabase_url
    from app.modules.schedules.infrastructure.mappers import (
        extract_calendrier_prevu_from_planned_calendar,
    )
    from app.modules.schedules.infrastructure.repository import schedule_repository

    print(f"Base ciblée : {supabase_url}")
    print(f"Mode        : {'APPLY (écriture)' if args.apply else 'simulation'}\n")

    companies = {
        c["id"]: c["company_name"]
        for c in supabase.table("companies").select("id, company_name").execute().data
        or []
    }
    employees = (
        supabase.table("employees")
        .select("id, company_id, first_name, last_name")
        .execute()
        .data
        or []
    )
    if args.company:
        employees = [
            e
            for e in employees
            if companies.get(e.get("company_id")) == args.company
        ]
    employee_ids = {str(e["id"]) for e in employees}
    noms = {
        str(e["id"]): f'{e.get("last_name") or ""} {e.get("first_name") or ""}'.strip()
        for e in employees
    }
    if not employee_ids:
        print("Aucun salarié dans le périmètre — rien à faire.")
        return 0

    absences = (
        supabase.table("absence_requests")
        .select("id, employee_id, type, selected_days")
        .eq("status", "validated")
        .execute()
        .data
        or []
    )
    absences = [a for a in absences if str(a.get("employee_id")) in employee_ids]
    grouped = days_by_employee_month(absences)

    par_mois: Dict[Tuple[int, int], List[str]] = defaultdict(list)
    for (employee_id, year, month) in grouped:
        par_mois[(year, month)].append(employee_id)

    a_ecrire: List[Dict[str, Any]] = []
    jours_marques = 0
    for (year, month), ids in sorted(par_mois.items()):
        rows = schedule_repository.list_schedules_for_employees(ids, year, month)
        for employee_id in ids:
            row = rows.get(employee_id)
            if not row:
                continue
            planned = row.get("planned_calendar") or {}
            calendrier = extract_calendrier_prevu_from_planned_calendar(planned)
            if not calendrier:
                continue
            marque, jours = mark_entries(
                calendrier, grouped[(employee_id, year, month)]
            )
            if not jours:
                continue
            nouveau_planned = dict(planned)
            nouveau_planned["calendrier_prevu"] = marque
            a_ecrire.append(
                {
                    "employee_id": employee_id,
                    "nom": noms.get(employee_id, "?"),
                    "societe": companies.get(
                        next(
                            (
                                e.get("company_id")
                                for e in employees
                                if str(e["id"]) == employee_id
                            ),
                            None,
                        ),
                        "?",
                    ),
                    "year": year,
                    "month": month,
                    "jours": sorted(jours),
                    "planned_calendar": nouveau_planned,
                }
            )
            jours_marques += len(jours)

    salaries = {c["employee_id"] for c in a_ecrire}
    resume = {
        "apply": args.apply,
        "demandes_validees_examinees": len(absences),
        "mois_de_planning_a_modifier": len(a_ecrire),
        "salaries_concernes": len(salaries),
        "jours_a_marquer": jours_marques,
        "detail": [
            {k: v for k, v in c.items() if k != "planned_calendar"} for c in a_ecrire
        ],
    }
    print(json.dumps(resume, ensure_ascii=False, indent=2))

    if not args.apply:
        print(
            f"\n{jours_marques} jour(s) seraient marqués sur "
            f"{len(salaries)} salarié(s)."
        )
        print("[simulation] Aucune écriture. Relancer avec --apply pour appliquer.")
        return 0

    if not a_ecrire:
        print("Rien à écrire.")
        return 0

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = _BACKEND / "scripts" / "data" / f"origine_absence-backup-{stamp}.json"
    backup.parent.mkdir(parents=True, exist_ok=True)
    backup.write_text(
        json.dumps(resume["detail"], ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Sauvegarde du périmètre : {backup}")

    for change in a_ecrire:
        schedule_repository.update_planned_calendar_only(
            change["employee_id"],
            change["year"],
            change["month"],
            change["planned_calendar"],
        )
    print(
        f"{jours_marques} jour(s) marqués sur {len(a_ecrire)} mois de planning."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
