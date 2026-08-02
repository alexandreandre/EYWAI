#!/usr/bin/env python3
"""Scanne les paliers médaille du travail de toutes les sociétés qui ont le module actif.

La détection n'était déclenchée que par l'activation du module ou le bouton
« Lancer le scan » : un salarié qui franchit un palier après coup n'était jamais
remonté. Ce script est appelé quotidiennement par GitHub Actions.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Compter les dossiers sans rien écrire en base.",
    )
    args = parser.parse_args(argv)
    dry_run = args.dry_run

    from app.core.database import supabase
    from app.modules.work_medals.application.detection import scan_company_work_medals
    from app.modules.work_medals.application.queries import get_work_medal_settings

    companies_resp = (
        supabase.table("companies")
        .select("id, company_name")
        .eq("is_active", True)
        .execute()
    )
    companies = list(companies_resp.data or [])

    results = []
    enabled_count = 0
    total_created = 0
    total_updated = 0
    errors = 0

    for company in companies:
        company_id = str(company.get("id") or "")
        if not company_id:
            continue
        try:
            settings = get_work_medal_settings(company_id)
            if not settings.enabled:
                continue
            enabled_count += 1
            outcome = scan_company_work_medals(company_id, dry_run=dry_run)
            total_created += outcome.created
            total_updated += outcome.updated
            results.append(
                {
                    "company_id": company_id,
                    "company_name": company.get("company_name"),
                    "created": outcome.created,
                    "updated": outcome.updated,
                    "tiers_configured": len(settings.tiers),
                }
            )
        except Exception as exc:  # noqa: BLE001 — une société KO ne bloque pas les autres
            errors += 1
            results.append(
                {
                    "company_id": company_id,
                    "company_name": company.get("company_name"),
                    "error": str(exc),
                }
            )

    summary = {
        "dry_run": dry_run,
        "companies_processed": len(companies),
        "companies_with_module_enabled": enabled_count,
        "total_created": total_created,
        "total_updated": total_updated,
        "errors": errors,
        "results": results,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    if enabled_count == 0:
        # Ne pas laisser un job « vert » masquer un module désactivé partout.
        print(
            "[work_medals] AVERTISSEMENT : aucune société n'a le module médailles activé.",
            file=sys.stderr,
        )
    return 0 if errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
