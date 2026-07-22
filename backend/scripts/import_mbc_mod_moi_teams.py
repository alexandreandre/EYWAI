#!/usr/bin/env python3
"""
Import idempotent des équipes MOI/MOD pour Mont Blanc Composite.

Lit `Config/MBC/Enrichissement Salarié/paie MBC.xlsx` (colonne Service),
crée les équipes MOI/MOD si absentes, affecte employees.team_id par rapprochement nom.

Usage (depuis backend/) :
  python scripts/import_mbc_mod_moi_teams.py
  python scripts/import_mbc_mod_moi_teams.py --apply
  python scripts/import_mbc_mod_moi_teams.py --file ../Config/MBC/.../paie\\ MBC.xlsx --company-id UUID

Prérequis : SUPABASE_URL + clé service role dans backend/.env
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.modules.admin_import.application.mbc_mod_moi_teams import (  # noqa: E402
    default_mbc_xlsx_path,
    run_mbc_mod_moi_teams_import,
)


def _print_report(report: dict) -> None:
    summary = report["summary"]
    print(f"Entreprise : {report.get('company_name')} ({report['company_id']})")
    print(f"Fichier    : {report.get('filename')}")
    print(f"Mode       : {'dry-run' if report['dry_run'] else 'apply'}")
    print()
    print("Équipes :")
    for name, info in sorted(report.get("teams", {}).items()):
        status = "à créer" if info.get("created") and not info.get("id") else info.get("id", "—")
        suffix = " (créée)" if info.get("created") and info.get("id") else ""
        print(f"  {name}: {status}{suffix}")
    print()
    print("Résumé :")
    print(f"  Lignes fichier          : {summary['rows_total']}")
    print(f"  Sorties (date sortie)   : {summary['rows_with_exit_date']}")
    print(f"  Sans MOI/MOD mappable   : {summary['rows_without_team_mapping']}")
    print(f"  Éligibles               : {summary['rows_eligible']}")
    print(f"  Service MOI / MOD / CAD : {summary['source_service_moi']} / "
          f"{summary['source_service_mod']} / {summary['source_service_cad']}")
    print(f"  Équipe MOI / MOD        : {summary['team_moi']} / {summary['team_mod']}")
    print(f"  Rapprochés              : {summary['matched']}")
    print(f"  Non rapprochés          : {summary['unmatched']}")
    if summary["ambiguous"]:
        print(f"  Ambigus                 : {summary['ambiguous']}")
    print(f"  Déjà corrects           : {summary['already_correct']}")
    print(f"  À affecter              : {summary['would_assign']}")
    print(f"  À réaffecter            : {summary['would_reassign']}")
    if not report["dry_run"]:
        print(f"  Affectés (apply)        : {summary['assigned']}")
        print(f"  Équipes créées          : {summary['teams_created']}")

    unmatched = report.get("unmatched") or []
    if unmatched:
        print()
        print("Non rapprochés :")
        for row in unmatched:
            print(
                f"  - {row['first_name']} {row['last_name']} "
                f"({row.get('service', '')} → {row.get('team_name', '')}) "
                f"[{row.get('reason', '')}]"
            )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Import MOI/MOD Mont Blanc Composite depuis export paie"
    )
    repo_root = _BACKEND_ROOT.parent
    parser.add_argument(
        "--file",
        type=Path,
        default=default_mbc_xlsx_path(repo_root),
        help="Chemin vers paie MBC.xlsx",
    )
    parser.add_argument(
        "--company-id",
        default=None,
        help="UUID entreprise (défaut : Mont Blanc Composite)",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Appliquer les affectations en base (défaut : dry-run)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Sortie JSON complète sur stdout",
    )
    args = parser.parse_args()

    dry_run = not args.apply
    if not args.file.exists():
        print(f"Fichier introuvable : {args.file}", file=sys.stderr)
        return 1

    content = args.file.read_bytes()
    try:
        report = run_mbc_mod_moi_teams_import(
            content=content,
            filename=args.file.name,
            company_id=args.company_id,
            dry_run=dry_run,
        )
    except (LookupError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        _print_report(report)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
