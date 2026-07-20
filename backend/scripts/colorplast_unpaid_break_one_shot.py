#!/usr/bin/env python3
"""
Correction ponctuelle Colorplast : retire 30 min (0,5 h) des heures faites
du lundi au jeudi pour chaque jour pointé, sauf Michel BUGNY et Leo COTTE.

Usage (depuis backend/) :
    python scripts/colorplast_unpaid_break_one_shot.py --dry-run
    python scripts/colorplast_unpaid_break_one_shot.py
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import date
from pathlib import Path
from typing import Any

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

from app.core.database import get_supabase_admin_client  # noqa: E402

COLORPLAST_COMPANY_ID = "dbe2b9f5-44dd-41bc-a625-36ed33d160f7"
UNPAID_BREAK_HOURS = 0.5
EXCLUDED_LAST_NAMES = {"BUGNY", "COTTE"}


def _normalize_name(value: str | None) -> str:
    import unicodedata

    text = (value or "").strip().upper()
    return "".join(
        c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn"
    )


def _is_excluded(last_name: str | None, first_name: str | None) -> bool:
    return _normalize_name(last_name) in EXCLUDED_LAST_NAMES


def _is_mon_to_thu(year: int, month: int, jour: int) -> bool:
    return date(year, month, jour).weekday() in (0, 1, 2, 3)


def _adjust_calendrier_reel(
    calendrier_reel: list[dict[str, Any]], year: int, month: int
) -> tuple[list[dict[str, Any]], int]:
    adjusted: list[dict[str, Any]] = []
    changes = 0
    for entry in calendrier_reel:
        jour = entry.get("jour")
        heures = entry.get("heures_faites")
        new_entry = dict(entry)
        if (
            jour is not None
            and heures is not None
            and float(heures) > 0
            and _is_mon_to_thu(year, month, int(jour))
        ):
            old = round(float(heures), 2)
            new = round(max(0.0, old - UNPAID_BREAK_HOURS), 2)
            if new != old:
                new_entry["heures_faites"] = new
                changes += 1
        adjusted.append(new_entry)
    return adjusted, changes


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Retire 30 min pause déj non payée (L-J) sur heures réelles Colorplast"
    )
    parser.add_argument("--dry-run", action="store_true", help="Aperçu sans écriture")
    args = parser.parse_args()

    client = get_supabase_admin_client()

    employees_resp = (
        client.table("employees")
        .select("id, first_name, last_name")
        .eq("company_id", COLORPLAST_COMPANY_ID)
        .execute()
    )
    employees = employees_resp.data or []
    target_ids = [
        str(e["id"])
        for e in employees
        if not _is_excluded(e.get("last_name"), e.get("first_name"))
    ]
    excluded_names = [
        f"{e.get('first_name')} {e.get('last_name')}"
        for e in employees
        if _is_excluded(e.get("last_name"), e.get("first_name"))
    ]

    print(f"Colorplast : {len(target_ids)} employé(s) ciblés")
    print(f"Exclus : {', '.join(excluded_names) or '(aucun)'}")

    if not target_ids:
        print("Aucun employé à traiter.")
        return 0

    schedules_resp = (
        client.table("employee_schedules")
        .select("id, employee_id, year, month, actual_hours")
        .eq("company_id", COLORPLAST_COMPANY_ID)
        .in_("employee_id", target_ids)
        .execute()
    )
    rows = schedules_resp.data or []

    total_rows = 0
    total_days = 0
    for row in rows:
        actual = row.get("actual_hours") or {}
        calendrier_reel = actual.get("calendrier_reel") or []
        if not calendrier_reel:
            continue

        year = int(row["year"])
        month = int(row["month"])
        adjusted, day_changes = _adjust_calendrier_reel(calendrier_reel, year, month)
        if day_changes == 0:
            continue

        emp = next((e for e in employees if str(e["id"]) == str(row["employee_id"])), {})
        emp_name = f"{emp.get('first_name', '')} {emp.get('last_name', '')}".strip()
        print(
            f"  {emp_name} — {month:02d}/{year} : {day_changes} jour(s) ajusté(s)"
        )
        total_rows += 1
        total_days += day_changes

        if args.dry_run:
            continue

        new_actual = dict(actual)
        new_actual["calendrier_reel"] = adjusted
        client.table("employee_schedules").update({"actual_hours": new_actual}).eq(
            "id", row["id"]
        ).execute()

    mode = "DRY-RUN" if args.dry_run else "APPLIQUÉ"
    print(f"\n{mode} : {total_rows} ligne(s) employee_schedules, {total_days} jour(s) modifié(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
