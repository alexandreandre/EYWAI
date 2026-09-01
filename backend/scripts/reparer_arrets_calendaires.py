#!/usr/bin/env python3
"""Répare les arrêts existants pour le décompte calendaire (spec 2026-09-01).

Avant ce lot, ① la saisie jour par jour laissait des trous (week-ends non
cliqués) dans `selected_days`, et ② la projection au calendrier ignorait les
week-ends même saisis. Pour chaque arrêt validé ciblé, ce script :

1. comble `selected_days` en période calendaire continue min→max (un
   enregistrement d'absence = UNE période, par construction du modèle) ;
2. re-projette le calendrier de paie via le même chemin que la validation
   (`update_calendar_from_days`, désormais déverrouillé pour les week-ends) —
   y compris quand rien n'est à combler : les week-ends déjà présents dans
   `selected_days` étaient ignorés par l'ancienne projection.

Cibles : `absence_requests` validées, type dans IJSS_ELIGIBLE_TYPES,
`arret_type != mi_temps_therapeutique` (travail partiel : jour par jour),
avec au moins un jour >= --depuis (défaut 2026-08-01 — ne pas toucher les
calendriers qui sous-tendent les bulletins Colorplast 01→06/2026 convergés).

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


def jours_apres_expansion(selected_days: List[Any]) -> Tuple[List[str], List[str]]:
    """(période calendaire complète min→max triée, jours ajoutés)."""
    parses = sorted({d for d in (_as_date(x) for x in selected_days or []) if d})
    if not parses:
        return [], []
    complets = [d.isoformat() for d in daterange_days(parses[0], parses[-1])]
    existants = {d.isoformat() for d in parses}
    return complets, [d for d in complets if d not in existants]


def arret_cible(row: Dict[str, Any], depuis: date) -> bool:
    """Arrêt validé, calendaire par nature, avec au moins un jour >= depuis."""
    if str(row.get("status") or "") != "validated":
        return False
    if str(row.get("type") or "") not in IJSS_ELIGIBLE_TYPES:
        return False
    if str(row.get("arret_type") or "") == "mi_temps_therapeutique":
        return False
    jours = [d for d in (_as_date(x) for x in row.get("selected_days") or []) if d]
    return bool(jours) and max(jours) >= depuis


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


def _reprojeter(row: Dict[str, Any], jours_iso: List[str]) -> None:
    """Rejoue la projection calendrier comme la validation d'absence."""
    from app.modules.absences.application import commands

    employee_id = str(row["employee_id"])
    absence_type = str(row["type"])
    jours = [date.fromisoformat(d) for d in jours_iso]
    historique = commands.build_historique_arrets_annee(
        employee_id, jours[0].year, exclude_request_id=str(row["id"])
    )
    sub = row.get("subrogation_active")
    commands.calendar_update_provider.update_calendar_from_days(
        employee_id,
        jours,
        absence_type,
        arret_type=str(row["arret_type"]) if row.get("arret_type") else None,
        subrogation_active=sub if isinstance(sub, bool) else None,
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
        help="ne traite que les arrêts ayant au moins un jour >= cette date",
    )
    args = parser.parse_args()

    from app.modules.absences.application import commands

    cibles = [r for r in _fetch_arrets_valides() if arret_cible(r, args.depuis)]
    total_ajoutes = 0
    for row in cibles:
        complets, ajoutes = jours_apres_expansion(row.get("selected_days") or [])
        total_ajoutes += len(ajoutes)
        etiquette = (
            f"{row['id']} employé={row['employee_id']} "
            f"{complets[0]}→{complets[-1]} ({row.get('type')}/{row.get('arret_type')})"
        )
        print(f"- {etiquette} : {len(ajoutes)} jour(s) à combler {ajoutes or ''}")
        if args.apply:
            if ajoutes:
                commands.absence_repository.update(
                    str(row["id"]), {"selected_days": complets}
                )
            _reprojeter(row, complets)
    mode = "APPLIQUÉ" if args.apply else "SIMULATION (rien écrit — relancer avec --apply)"
    print(f"\n{len(cibles)} arrêt(s) ciblé(s), {total_ajoutes} jour(s) comblé(s) — {mode}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
