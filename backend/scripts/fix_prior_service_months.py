#!/usr/bin/env python3
"""Corrige `employees.prior_service_months` (reprise d'ancienneté).

L'import de l'export paie recopiait la colonne « Nb jour anc. » — qui porte
l'ancienneté TOTALE à la date d'extraction — dans un champ que le moteur retranche
de `hire_date`. Résultat : ancienneté doublée pour tous ceux dont l'ancienneté
démarre à l'embauche. Le parser est corrigé (`payroll_export_parser.
resolve_prior_service_months`) ; ce script répare les fiches déjà importées.

La reprise réelle est reconstituée en refaisant à l'envers le calcul de l'import :
on repart des jours d'ancienneté (valeur stockée x 30, la conversion faite à
l'époque), on les retranche de la date d'import de la fiche pour retrouver le point
de départ d'ancienneté, et on ne garde que ce qui précède l'embauche — via la même
fonction que le parser corrigé, pour que les deux chemins donnent le même résultat.

Sans `--apply`, le script n'écrit rien. Avec `--apply`, il enregistre d'abord une
sauvegarde JSON des valeurs actuelles.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path

_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))


def _months_between(start: date, end: date) -> int:
    if start >= end:
        return 0
    months = (end.year - start.year) * 12 + (end.month - start.month)
    if end.day < start.day:
        months -= 1
    return max(0, months)


def _as_date(raw: str | None) -> date | None:
    if not raw:
        return None
    try:
        return date.fromisoformat(str(raw)[:10])
    except (TypeError, ValueError):
        return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Écrire en base.")
    parser.add_argument("--company", help="Limiter à une société (nom exact).")
    args = parser.parse_args(argv)

    from app.core.database import supabase
    from app.modules.admin_import.application.payroll_export_parser import (
        resolve_prior_service_months,
    )

    companies = {
        c["id"]: c["company_name"]
        for c in supabase.table("companies").select("id, company_name").execute().data
        or []
    }
    rows = (
        supabase.table("employees")
        .select("id, company_id, first_name, last_name, hire_date, "
                "prior_service_months, created_at")
        .execute()
        .data
        or []
    )

    changes: list[dict] = []
    kept: list[dict] = []
    for emp in rows:
        company = companies.get(emp["company_id"], "?")
        if args.company and company != args.company:
            continue
        current = int(emp.get("prior_service_months") or 0)
        if current <= 0:
            continue
        hire = _as_date(emp.get("hire_date"))
        imported = _as_date(emp.get("created_at")) or date.today()
        target = resolve_prior_service_months(
            current * 30, emp.get("hire_date"), imported
        )
        target = 0 if target is None else target
        entry = {
            "employee_id": emp["id"],
            "company": company,
            "nom": f'{emp.get("last_name")} {emp.get("first_name")}'.strip(),
            "hire_date": emp.get("hire_date"),
            "anciennete_ecoulee_mois": _months_between(hire, imported) if hire else 0,
            "prior_actuel": current,
            "prior_corrige": target,
        }
        (changes if target != current else kept).append(entry)

    reprises = [c for c in changes if c["prior_corrige"] > 0]
    summary = {
        "apply": args.apply,
        "fiches_a_corriger": len(changes),
        "dont_remises_a_zero": len(changes) - len(reprises),
        "dont_reprise_reelle_conservee": len(reprises),
        "fiches_inchangees": len(kept),
        "reprises_reelles": sorted(reprises, key=lambda c: -c["prior_corrige"]),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    if not args.apply:
        print("\n[dry-run] Aucune écriture. Relancer avec --apply pour appliquer.")
        return 0

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = _BACKEND / "scripts" / "data" / f"prior_service_months-backup-{stamp}.json"
    backup.parent.mkdir(parents=True, exist_ok=True)
    backup.write_text(
        json.dumps(changes + kept, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Sauvegarde : {backup}")

    for entry in changes:
        supabase.table("employees").update(
            {"prior_service_months": entry["prior_corrige"]}
        ).eq("id", entry["employee_id"]).execute()
    print(f"{len(changes)} fiche(s) mise(s) à jour.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
