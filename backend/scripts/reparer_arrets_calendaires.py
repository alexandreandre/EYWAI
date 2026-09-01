#!/usr/bin/env python3
"""Répare les arrêts existants pour le décompte calendaire (spec 2026-09-01).

Avant ce lot, la saisie jour par jour laissait des trous (week-ends non
cliqués) dans `selected_days`, et le calendrier de paie ne portait pas les
vraies bornes de l'arrêt. Pour chaque arrêt validé ciblé, ce script :

1. comble `selected_days` avec les week-ends manquants ENTRE min et max —
   uniquement si tous les jours manquants sont des samedis/dimanches : un trou
   en semaine peut être une reprise de travail réelle (deux épisodes saisis en
   un enregistrement) et est signalé pour arbitrage manuel, jamais comblé ;
2. re-projette le calendrier de paie via le même chemin que la validation
   (`update_calendar_from_days`) : les bornes date_debut/date_fin_arret_reel
   et les métadonnées sont (re)posées sur les jours d'arrêt, sans retyper les
   jours non travaillés.

Cibles : `absence_requests` validées, type dans IJSS_ELIGIBLE_TYPES,
`arret_type != mi_temps_therapeutique` (travail partiel : jour par jour),
dont TOUS les jours sont >= --depuis (défaut 2026-08-01) : un arrêt à cheval
sur la borne est signalé mais non traité, pour ne pas réécrire les calendriers
qui sous-tendent les bulletins Colorplast 01→06/2026 convergés.

Déroulé en deux passes (avec --apply) : d'abord tous les selected_days sont
comblés, puis chaque arrêt est re-projeté — l'historique des arrêts de l'année
est ainsi calculé sur des données déjà réparées. Une erreur sur une ligne est
rapportée et n'interrompt pas les suivantes ; le script est rejouable.

Sans `--apply`, rien n'est écrit : rapport de simulation seulement.

Usage :
    venv/bin/python -m scripts.reparer_arrets_calendaires
    venv/bin/python -m scripts.reparer_arrets_calendaires --depuis 2026-08-01 --apply
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from app.modules.absences.domain.enums import IJSS_ELIGIBLE_TYPES  # noqa: E402
from app.shared.domain.absence_calendar import daterange_days  # noqa: E402


def _as_date(raw: Any) -> Optional[date]:
    """Convertit une entrée de `selected_days` (str ISO ou date) en date."""
    if raw is None or raw == "":
        return None
    if isinstance(raw, datetime):
        return raw.date()
    if isinstance(raw, date):
        return raw
    try:
        return date.fromisoformat(str(raw)[:10])
    except (TypeError, ValueError):
        return None


def jours_apres_expansion(
    selected_days: List[Any],
) -> Tuple[List[str], List[str], List[str]]:
    """(jours après comblement, week-ends ajoutés, trous EN SEMAINE non comblés).

    Seuls les samedis/dimanches manquants entre min et max sont comblés. Un jour
    de semaine manquant peut être une reprise réelle de travail : il est
    rapporté dans le 3e élément et RIEN n'est comblé pour cet arrêt.
    """
    parses = sorted({d for d in (_as_date(x) for x in selected_days or []) if d})
    if not parses:
        return [], [], []
    existants = {d.isoformat() for d in parses}
    manquants = [
        d for d in daterange_days(parses[0], parses[-1]) if d.isoformat() not in existants
    ]
    trous_semaine = [d.isoformat() for d in manquants if d.weekday() < 5]
    if trous_semaine:
        return [d.isoformat() for d in parses], [], trous_semaine
    ajoutes = [d.isoformat() for d in manquants]
    complets = sorted(existants | set(ajoutes))
    return complets, ajoutes, []


def arret_cible(row: Dict[str, Any], depuis: date) -> bool:
    """Arrêt validé, calendaire par nature, entièrement >= depuis."""
    if str(row.get("status") or "") != "validated":
        return False
    if str(row.get("type") or "") not in IJSS_ELIGIBLE_TYPES:
        return False
    if str(row.get("arret_type") or "") == "mi_temps_therapeutique":
        return False
    jours = [d for d in (_as_date(x) for x in row.get("selected_days") or []) if d]
    return bool(jours) and min(jours) >= depuis


def arret_a_cheval(row: Dict[str, Any], depuis: date) -> bool:
    """Arrêt validé de type ciblé qui chevauche la borne (min < depuis <= max)."""
    if str(row.get("status") or "") != "validated":
        return False
    if str(row.get("type") or "") not in IJSS_ELIGIBLE_TYPES:
        return False
    if str(row.get("arret_type") or "") == "mi_temps_therapeutique":
        return False
    jours = [d for d in (_as_date(x) for x in row.get("selected_days") or []) if d]
    return bool(jours) and min(jours) < depuis <= max(jours)


def _fetch_arrets_valides() -> List[Dict[str, Any]]:
    """Toutes les demandes validées de type arrêt (lecture paginée)."""
    from app.core.database import supabase
    from app.modules.absences.infrastructure.pagination import fetch_all_rows

    def page(offset: int, limit: int) -> List[Dict[str, Any]]:
        resp = (
            supabase.table("absence_requests")
            .select(
                "id, employee_id, company_id, type, arret_type, status, "
                "selected_days, subrogation_active"
            )
            .eq("status", "validated")
            .in_("type", sorted(IJSS_ELIGIBLE_TYPES))
            .order("id")
            .range(offset, offset + limit - 1)
            .execute()
        )
        return resp.data or []

    return fetch_all_rows(page)


def _resoudre_subrogation(row: Dict[str, Any]) -> Optional[bool]:
    """Comme la validation : calcule la subrogation si elle n'est pas stockée."""
    sub = row.get("subrogation_active")
    if isinstance(sub, bool):
        return sub
    if not row.get("arret_type"):
        return None
    from app.core.database import supabase
    from app.modules.absences.application.commands import (
        compute_subrogation_for_absence,
        get_maintenance_settings,
    )

    emp_res = (
        supabase.table("employees")
        .select("*")
        .eq("id", row["employee_id"])
        .maybe_single()
        .execute()
    )
    employee_row = emp_res.data if emp_res else None
    if not employee_row:
        return None
    settings_dict = get_maintenance_settings(
        str(row.get("company_id") or "")
    ).model_dump(mode="json")
    return bool(
        compute_subrogation_for_absence(row, employee_row, settings_dict, override=None)
    )


def _reprojeter(row: Dict[str, Any], jours_iso: List[str]) -> None:
    """Rejoue la projection calendrier comme la validation d'absence."""
    from app.modules.absences.application import commands

    employee_id = str(row["employee_id"])
    absence_type = str(row["type"])
    jours = [date.fromisoformat(d) for d in jours_iso]
    historique = commands.build_historique_arrets_annee(
        employee_id, jours[0].year, exclude_request_id=str(row["id"])
    )
    commands.calendar_update_provider.update_calendar_from_days(
        employee_id,
        jours,
        absence_type,
        arret_type=str(row["arret_type"]) if row.get("arret_type") else None,
        subrogation_active=_resoudre_subrogation(row),
        nombre_enfants=commands.resolve_nombre_enfants_employee(employee_id),
        historique_arrets_annee=historique or None,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Répare les arrêts existants en périodes calendaires."
    )
    parser.add_argument(
        "--apply", action="store_true", help="écrit (défaut : simulation)"
    )
    parser.add_argument(
        "--depuis",
        type=date.fromisoformat,
        default=date(2026, 8, 1),
        help="ne traite que les arrêts entièrement >= cette date",
    )
    args = parser.parse_args()

    from app.modules.absences.application import commands

    lignes = _fetch_arrets_valides()
    cibles = [r for r in lignes if arret_cible(r, args.depuis)]
    a_cheval = [r for r in lignes if arret_a_cheval(r, args.depuis)]
    for row in a_cheval:
        jours = sorted(
            d.isoformat()
            for d in (_as_date(x) for x in row.get("selected_days") or [])
            if d
        )
        print(
            f"! {row['id']} employé={row['employee_id']} {jours[0]}→{jours[-1]} : "
            f"À CHEVAL sur --depuis {args.depuis}, non traité (arbitrage manuel)"
        )

    total_ajoutes = 0
    erreurs: List[str] = []
    plan: List[Tuple[Dict[str, Any], List[str], List[str]]] = []
    for row in cibles:
        complets, ajoutes, trous_semaine = jours_apres_expansion(
            row.get("selected_days") or []
        )
        etiquette = (
            f"{row['id']} employé={row['employee_id']} "
            f"{complets[0]}→{complets[-1]} ({row.get('type')}/{row.get('arret_type')})"
        )
        if trous_semaine:
            print(
                f"! {etiquette} : trous EN SEMAINE {trous_semaine} — non comblé, "
                "arbitrage manuel (reprise de travail ? deux arrêts en un ?)"
            )
            continue
        total_ajoutes += len(ajoutes)
        print(f"- {etiquette} : {len(ajoutes)} week-end(s) à combler {ajoutes or ''}")
        plan.append((row, complets, ajoutes))

    if args.apply:
        # Passe 1 : combler tous les selected_days d'abord, pour que la passe 2
        # calcule l'historique des arrêts sur des données déjà réparées.
        for row, complets, ajoutes in plan:
            if not ajoutes:
                continue
            try:
                commands.absence_repository.update(
                    str(row["id"]), {"selected_days": complets}
                )
            except Exception as exc:  # noqa: BLE001 — rapport, on continue
                erreurs.append(f"{row['id']} (selected_days) : {exc}")
        # Passe 2 : re-projection (bornes réelles + métadonnées rafraîchies).
        for row, complets, _ajoutes in plan:
            try:
                _reprojeter(row, complets)
            except Exception as exc:  # noqa: BLE001 — rapport, on continue
                erreurs.append(f"{row['id']} (projection) : {exc}")

    mode = "APPLIQUÉ" if args.apply else "SIMULATION (rien écrit — relancer avec --apply)"
    print(
        f"\n{len(plan)} arrêt(s) traité(s), {total_ajoutes} jour(s) comblé(s), "
        f"{len(a_cheval)} à cheval ignoré(s) — {mode}"
    )
    if erreurs:
        print(f"\n{len(erreurs)} erreur(s) — corriger puis relancer (rejouable) :")
        for e in erreurs:
            print(f"  ✗ {e}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
