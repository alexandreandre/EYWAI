"""Pose une absence maladie/rechute PLEIN MOIS (sans maintien) : convertit tous
les jours 'travail' du planned_calendar en absence_non_remuneree, vide
actual_hours (pointage non pertinent), et ajoute optionnellement la
participation numéraire manquante. Revert-safe (garde si tier-S baisse).

Usage : .venv/bin/python -m scripts.backtest.full_month_absence MAT [--participation MONTANT] [--avance MONTANT]
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.core.database import get_supabase_admin_client
from scripts.backtest.employee_matching import match_employees, resolve_company_id
from scripts.backtest.pdf_loader import load_reference_bulletins
from scripts.backtest.mbc_reconcile import (
    COMPANY, YEAR, MONTH, CONVERGENCE, tier_s, take_snapshot, restore_snapshot,
)


def main():
    args = sys.argv[1:]
    participation = None
    avance = None
    if "--participation" in args:
        i = args.index("--participation")
        participation = float(args[i + 1])
        args = args[:i] + args[i + 2:]
    if "--avance" in args:
        i = args.index("--avance")
        avance = float(args[i + 1])
        args = args[:i] + args[i + 2:]
    mats = set(args)

    admin = get_supabase_admin_client()
    refs = load_reference_bulletins(COMPANY, YEAR, MONTH)
    cid = resolve_company_id(COMPANY)
    matched = [m for m in match_employees(cid, refs).matched if m.matricule in mats]

    for m in matched:
        before = tier_s(m)
        snap = take_snapshot(admin, m.employee_id, cid)
        try:
            sched = (admin.table("employee_schedules")
                     .select("id,planned_calendar,actual_hours")
                     .match({"employee_id": m.employee_id, "year": YEAR, "month": MONTH})
                     .maybe_single().execute())
            if not sched or not sched.data:
                print(f"[{m.matricule}] pas de schedule, skip")
                continue
            planned = copy.deepcopy(sched.data.get("planned_calendar") or {})
            cal = planned.get("calendrier_prevu", [])
            for j in cal:
                if j.get("type") == "travail":
                    j["type"] = "absence_non_remuneree"
                    j["manuel"] = True
            planned["calendrier_prevu"] = cal
            actual = copy.deepcopy(sched.data.get("actual_hours") or {})
            actual["calendrier_reel"] = []
            actual["mois_sans_pointage"] = True
            admin.table("employee_schedules").update({
                "planned_calendar": planned, "actual_hours": actual,
            }).eq("id", sched.data["id"]).execute()

            if participation is not None:
                admin.table("monthly_inputs").insert({
                    "employee_id": m.employee_id, "company_id": cid,
                    "year": YEAR, "month": MONTH,
                    "name": "Participation 2025 — numéraire",
                    "amount": participation, "is_socially_taxed": False,
                    "is_taxable": True,
                }).execute()
            if avance is not None:
                admin.table("monthly_inputs").insert({
                    "employee_id": m.employee_id, "company_id": cid,
                    "year": YEAR, "month": MONTH,
                    "name": "Avance participation 2025 (déjà versée)",
                    "amount": avance, "is_socially_taxed": False,
                    "is_taxable": False,
                }).execute()

            after = tier_s(m)
            if after < before:
                print(f"[{m.matricule}] {before:.2f} -> {after:.2f} amélioré")
            else:
                print(f"[{m.matricule}] {before:.2f} -> {after:.2f} revert (essai={after:.2f})")
                restore_snapshot(admin, m.employee_id, cid, snap)
                tier_s(m)
        except Exception as exc:
            print(f"[{m.matricule}] EXCEPTION {exc} -> revert")
            restore_snapshot(admin, m.employee_id, cid, snap)
            tier_s(m)


if __name__ == "__main__":
    main()
