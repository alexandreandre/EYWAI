#!/usr/bin/env python3
"""
Seed idempotent des calendriers horaires prévisionnels 2026.

Pour chaque société ciblée : applique le preset (modèles + plans éditables) puis
génère l'année dans employee_schedules.planned_calendar.calendrier_prevu pour tous
les salariés concernés, dans l'ordre de précédence (société → équipe → salariés)
afin que les exceptions salarié priment.

Idempotent : ré-exécutable sans dupliquer les plans (mise à jour par nom).

Usage :
    python scripts/seed_schedule_calendars_2026.py --dry-run          # aperçu global
    python scripts/seed_schedule_calendars_2026.py                    # applique tout
    python scripts/seed_schedule_calendars_2026.py --company <UUID> --preset cartol
    python scripts/seed_schedule_calendars_2026.py --year 2026 --recalc-payroll

Le mapping société→preset est résolu automatiquement par nom (contient), ou
fourni explicitement via --company / --preset (répétables).
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

env_file = BACKEND_ROOT / ".env"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"'))

from app.core.database import supabase  # noqa: E402
from app.modules.schedules.application.preset_apply import apply_preset  # noqa: E402
from app.modules.schedules.application.calendar_generation import (  # noqa: E402
    generate_all_active_plans,
)
from app.modules.schedules.application.presets_2026 import get_registry  # noqa: E402

# Motifs de correspondance nom de société → clé de preset (nom en minuscules, "contient").
NAME_MATCHERS = {
    "comitech": "comitech",
    "colorplast": "colorplast",
    "mont blanc": "mbc",   # MBC = Mont Blanc Composite
    "mbc": "mbc",
    "lewis": "lewis",
    "cartol": "cartol",
}


def _list_companies() -> list[dict]:
    resp = supabase.table("companies").select("id, company_name").execute()
    return resp.data or []


def _auto_map(companies: list[dict]) -> list[tuple[str, str, str]]:
    """Retourne [(company_id, company_name, preset_key)] par correspondance de nom."""
    out: list[tuple[str, str, str]] = []
    for co in companies:
        name = (co.get("company_name") or "").lower()
        for needle, key in NAME_MATCHERS.items():
            if needle in name:
                out.append((str(co["id"]), co.get("company_name") or "", key))
                break
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed calendriers horaires 2026")
    parser.add_argument("--dry-run", action="store_true", help="Aperçu, aucune écriture")
    parser.add_argument("--year", type=int, default=2026)
    parser.add_argument("--recalc-payroll", action="store_true")
    parser.add_argument(
        "--company", action="append", default=[], help="UUID société (répétable)"
    )
    parser.add_argument(
        "--preset", action="append", default=[], help="Clé preset (répétable, aligné à --company)"
    )
    args = parser.parse_args()

    registry = get_registry()

    # Cibles explicites ou auto-mapping par nom.
    if args.company:
        if len(args.preset) != len(args.company):
            print("❌ --preset doit être fourni autant de fois que --company.")
            return 2
        targets = list(zip(args.company, ["?"] * len(args.company), args.preset))
    else:
        targets = _auto_map(_list_companies())

    if not targets:
        print("⚠️  Aucune société cible trouvée (mapping par nom vide).")
        return 1

    print(f"{'APERÇU (dry-run)' if args.dry_run else 'GÉNÉRATION RÉELLE'} — année {args.year}\n")
    total_writes = 0
    for company_id, company_name, preset_key in targets:
        if preset_key not in registry:
            print(f"  ⏭  {company_name or company_id}: preset inconnu '{preset_key}', ignoré.")
            continue

        label = registry[preset_key].company_label
        print(f"▶ {company_name or company_id}  →  preset '{preset_key}' ({label})")

        # 1) Applique le preset (idempotent). On n'écrit pas les plans en dry-run.
        if not args.dry_run:
            applied = apply_preset(company_id, preset_key)
            print(
                f"    modèles: {applied['templates_created']} · plans: {applied['plans_created']}"
            )
        else:
            print("    (dry-run : preset non matérialisé, génération simulée sur les plans existants)")

        # 2) Génère tous les plans actifs, en précédence — progression affichée en direct.
        def _progress(p: dict) -> None:
            detail = (
                p.get("reason")
                if p.get("status") == "skipped"
                else f"{p.get('employee_count', 0)} salarié(s)"
            )
            print(f"    · {p.get('plan_name')} [{p.get('scope_type')}] → {detail}", flush=True)

        result = generate_all_active_plans(
            company_id,
            year=args.year,
            dry_run=args.dry_run,
            recalculate_payroll=args.recalc_payroll,
            on_plan_done=_progress,
        )
        total_writes += result.get("employee_writes", 0)
        print()

    verb = "simulé(s)" if args.dry_run else "écrit(s)"
    print(f"✅ Terminé — {total_writes} calendrier(s) salarié {verb}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
