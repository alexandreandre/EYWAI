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
  (cf. `app.shared.domain.absence_calendar.ABSENCE_CALENDAR_TYPES`) ;
- `type` et `heures_prevues` ne sont JAMAIS modifiés ;
- un jour portant déjà une clé `origine` est laissé tel quel : le script est
  idempotent et rejouable.

Le rapport JSON porte aussi un inventaire `absences_perdues` : les jours
d'absences validées dont le planning porte aujourd'hui un autre type (ou plus
de jour du tout). Ce sont les salariés déjà lésés — le script ne corrige
**rien** de ce côté, il se contente de les lister pour arbitrage RH.

Sans `--apply`, rien n'est écrit : le compte rendu de simulation est affiché.
Avec `--apply`, une sauvegarde JSON contenant le calendrier d'avant est écrite,
et `--revert FICHIER` la rejoue à l'envers.

Usage :
    venv/bin/python -m scripts.backfill_origine_absence
    venv/bin/python -m scripts.backfill_origine_absence --company "Colorplast"
    venv/bin/python -m scripts.backfill_origine_absence --apply
    venv/bin/python -m scripts.backfill_origine_absence --revert FICHIER
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from app.modules.absences.infrastructure.pagination import (  # noqa: E402
    DEFAULT_PAGE_SIZE,
    fetch_all_rows,
)
from app.shared.domain.absence_calendar import (  # noqa: E402
    ABSENCE_CALENDAR_TYPES,
    ORIGINE_ABSENCE,
)


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


def _jour(raw: Any) -> Optional[int]:
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


# ----- Lectures paginées (PostgREST tronque silencieusement à 1 000 lignes) ---


def fetch_companies(client: Any) -> List[Dict[str, Any]]:
    def page(offset: int, limit: int) -> List[Dict[str, Any]]:
        resp = (
            client.table("companies")
            .select("id, company_name")
            .order("id")
            .range(offset, offset + limit - 1)
            .execute()
        )
        return resp.data or []

    return fetch_all_rows(page)


def fetch_employees(
    client: Any, *, company_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Salariés du périmètre — le filtre société est poussé dans la requête."""

    def page(offset: int, limit: int) -> List[Dict[str, Any]]:
        query = client.table("employees").select(
            "id, company_id, first_name, last_name"
        )
        if company_id:
            query = query.eq("company_id", company_id)
        resp = query.order("id").range(offset, offset + limit - 1).execute()
        return resp.data or []

    return fetch_all_rows(page)


def fetch_validated_absences(
    client: Any, employee_ids: List[str]
) -> List[Dict[str, Any]]:
    """Demandes validées des salariés du périmètre, par lots d'identifiants."""
    if not employee_ids:
        return []
    rows: List[Dict[str, Any]] = []
    lot = 200
    for i in range(0, len(employee_ids), lot):
        batch = employee_ids[i : i + lot]

        def page(offset: int, limit: int, _batch=batch) -> List[Dict[str, Any]]:
            resp = (
                client.table("absence_requests")
                .select("id, employee_id, type, selected_days")
                .eq("status", "validated")
                .in_("employee_id", _batch)
                .order("id")
                .range(offset, offset + limit - 1)
                .execute()
            )
            return resp.data or []

        rows.extend(fetch_all_rows(page, page_size=DEFAULT_PAGE_SIZE))
    return rows


# ----- Règles pures --------------------------------------------------------


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
        jour = _jour(nouvelle.get("jour"))
        if jour is None:
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


def absences_perdues(
    calendrier_prevu: List[Dict[str, Any]], jours: Set[int]
) -> List[Dict[str, Any]]:
    """Jours d'absence validée que le planning ne reflète plus.

    Le planning porte un autre type — ou plus aucun jour. Ces salariés sont
    déjà lésés : le script les LISTE, il ne corrige rien automatiquement
    (rétablir un arrêt effacé demande un arbitrage RH, pas un script).
    """
    types_par_jour: Dict[int, Any] = {}
    for entree in calendrier_prevu:
        jour = _jour(entree.get("jour"))
        if jour is not None:
            types_par_jour[jour] = entree.get("type")
    perdues: List[Dict[str, Any]] = []
    for jour in sorted(jours):
        type_planning = types_par_jour.get(jour)
        if type_planning not in ABSENCE_CALENDAR_TYPES:
            perdues.append({"jour": jour, "type_planning": type_planning})
    return perdues


# ----- Sauvegarde et retour arrière ---------------------------------------


def write_backup(chemin: Path, changements: List[Dict[str, Any]]) -> None:
    """Écrit la sauvegarde, calendrier d'AVANT compris (sinon pas de revert)."""
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(
        json.dumps(changements, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def do_revert(
    chemin: Path,
    *,
    write_planned_calendar: Callable[[str, int, int, Dict[str, Any]], None],
) -> int:
    """Rejoue une sauvegarde à l'envers : réécrit le calendrier d'avant."""
    if not chemin.exists():
        print(f"Sauvegarde introuvable : {chemin}")
        return 1
    changements = json.loads(chemin.read_text(encoding="utf-8"))
    sans_avant = [c for c in changements if "planned_calendar_avant" not in c]
    if sans_avant:
        print(
            f"{len(sans_avant)} entrée(s) sans `planned_calendar_avant` : "
            "sauvegarde antérieure au retour arrière, restauration impossible."
        )
        return 2
    for change in changements:
        write_planned_calendar(
            change["employee_id"],
            change["year"],
            change["month"],
            change["planned_calendar_avant"],
        )
    print(f"{len(changements)} mois de planning restauré(s) depuis {chemin}.")
    return 0


# ----- Programme ------------------------------------------------------------


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--apply", action="store_true", help="Écrire en base (sinon simulation)."
    )
    parser.add_argument("--company", help="Limiter à une société (nom exact).")
    parser.add_argument("--revert", metavar="FICHIER", help="Restaurer une sauvegarde.")
    args = parser.parse_args(argv)

    from app.core.database import supabase, supabase_url
    from app.modules.schedules.infrastructure.mappers import (
        extract_calendrier_prevu_from_planned_calendar,
    )
    from app.modules.schedules.infrastructure.repository import schedule_repository

    print(f"Base ciblée : {supabase_url}")

    if args.revert:
        return do_revert(
            Path(args.revert),
            write_planned_calendar=schedule_repository.update_planned_calendar_only,
        )

    print(f"Mode        : {'APPLY (écriture)' if args.apply else 'simulation'}\n")

    companies = {c["id"]: c["company_name"] for c in fetch_companies(supabase)}
    company_id = None
    if args.company:
        company_id = next(
            (cid for cid, nom in companies.items() if nom == args.company), None
        )
        if company_id is None:
            print(f"Société « {args.company} » introuvable.")
            return 1

    employees = fetch_employees(supabase, company_id=company_id)
    employee_ids = [str(e["id"]) for e in employees]
    noms = {
        str(e["id"]): f'{e.get("last_name") or ""} {e.get("first_name") or ""}'.strip()
        for e in employees
    }
    societes = {str(e["id"]): companies.get(e.get("company_id"), "?") for e in employees}
    if not employee_ids:
        print("Aucun salarié dans le périmètre — rien à faire.")
        return 0

    absences = fetch_validated_absences(supabase, employee_ids)
    grouped = days_by_employee_month(absences)

    par_mois: Dict[Tuple[int, int], List[str]] = defaultdict(list)
    for employee_id, year, month in grouped:
        par_mois[(year, month)].append(employee_id)

    a_ecrire: List[Dict[str, Any]] = []
    perdues_globales: List[Dict[str, Any]] = []
    jours_marques = 0
    for (year, month), ids in sorted(par_mois.items()):
        rows = schedule_repository.list_schedules_for_employees(ids, year, month)
        for employee_id in ids:
            jours = grouped[(employee_id, year, month)]
            row = rows.get(employee_id)
            if not row:
                perdues_globales.append(
                    {
                        "employee_id": employee_id,
                        "nom": noms.get(employee_id, "?"),
                        "societe": societes.get(employee_id, "?"),
                        "year": year,
                        "month": month,
                        "jours": [
                            {"jour": j, "type_planning": None} for j in sorted(jours)
                        ],
                        "motif": "aucun planning pour ce mois",
                    }
                )
                continue
            planned = row.get("planned_calendar") or {}
            calendrier = extract_calendrier_prevu_from_planned_calendar(planned)

            perdues = absences_perdues(calendrier, jours)
            if perdues:
                perdues_globales.append(
                    {
                        "employee_id": employee_id,
                        "nom": noms.get(employee_id, "?"),
                        "societe": societes.get(employee_id, "?"),
                        "year": year,
                        "month": month,
                        "jours": perdues,
                        "motif": "le planning porte un autre type",
                    }
                )

            if not calendrier:
                continue
            marque, jours_ok = mark_entries(calendrier, jours)
            if not jours_ok:
                continue
            nouveau_planned = dict(planned)
            nouveau_planned["calendrier_prevu"] = marque
            a_ecrire.append(
                {
                    "employee_id": employee_id,
                    "nom": noms.get(employee_id, "?"),
                    "societe": societes.get(employee_id, "?"),
                    "year": year,
                    "month": month,
                    "jours": sorted(jours_ok),
                    "planned_calendar": nouveau_planned,
                    "planned_calendar_avant": planned,
                }
            )
            jours_marques += len(jours_ok)

    salaries = {c["employee_id"] for c in a_ecrire}
    resume = {
        "apply": args.apply,
        "demandes_validees_examinees": len(absences),
        "mois_de_planning_a_modifier": len(a_ecrire),
        "salaries_concernes": len(salaries),
        "jours_a_marquer": jours_marques,
        "detail": [
            {
                k: v
                for k, v in c.items()
                if k not in ("planned_calendar", "planned_calendar_avant")
            }
            for c in a_ecrire
        ],
        "absences_perdues": perdues_globales,
    }
    print(json.dumps(resume, ensure_ascii=False, indent=2))

    if perdues_globales:
        total = sum(len(p["jours"]) for p in perdues_globales)
        print(
            f"\n⚠ {total} jour(s) d'absence validée ne sont plus reflétés dans le "
            f"planning, sur {len({p['employee_id'] for p in perdues_globales})} "
            "salarié(s). Rien n'est corrigé automatiquement : ces jours "
            "demandent un arbitrage RH."
        )

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
    write_backup(backup, a_ecrire)
    print(f"Sauvegarde (calendrier d'avant compris) : {backup}")

    for change in a_ecrire:
        schedule_repository.update_planned_calendar_only(
            change["employee_id"],
            change["year"],
            change["month"],
            change["planned_calendar"],
        )
    print(f"{jours_marques} jour(s) marqués sur {len(a_ecrire)} mois de planning.")
    print(f"Retour arrière : --revert {backup}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
