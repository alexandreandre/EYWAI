#!/usr/bin/env python3
"""
Rétrocompatibilité — préférer setup_comitech_composite.py.

Ce shim relance uniquement la partie formations / habilitations / budget
pour Comitech Composite (registre Excel RH), sans reconfigurer l'entreprise
ni le suivi médical.

Usage (depuis backend/, venv activé) :
  python scripts/setup_comitech_composite.py              # config complète (recommandé)
  python scripts/seed_comitech_formation.py [--dry-run]   # formations seules
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_ROOT = Path(__file__).resolve().parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

env_file = BACKEND_ROOT / ".env"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"'))

from setup_comitech_composite import (  # noqa: E402
    COMPANY_NAME,
    SetupOptions,
    find_company,
    load_comitech_employees,
    run_comitech_composite_setup,
    seed_formation_registry,
    _get_supabase,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Seed formations Comitech Composite (shim — voir setup_comitech_composite.py)"
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--full-setup",
        action="store_true",
        help="Lancer setup_comitech_composite.py complet au lieu des formations seules",
    )
    args = parser.parse_args()

    if args.full_setup:
        summary = run_comitech_composite_setup(
            SetupOptions(dry_run=args.dry_run, scan_medals=not args.dry_run)
        )
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        return 0

    supabase = _get_supabase()
    company = find_company(supabase)
    if not company:
        print(
            f"Entreprise « {COMPANY_NAME} » introuvable — "
            f"lancer d'abord : python scripts/setup_comitech_composite.py",
            file=sys.stderr,
        )
        return 1

    company_id = str(company["id"])
    print(f"Comitech Composite : {company.get('company_name')} ({company_id})")

    employees = load_comitech_employees(
        supabase, company_id, dry_run=args.dry_run, ensure_stubs=True
    )
    print(f"Effectif : {len(employees)} salarié(s)")

    formation_summary = seed_formation_registry(
        supabase, company_id, employees, dry_run=args.dry_run
    )
    print(json.dumps(formation_summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
