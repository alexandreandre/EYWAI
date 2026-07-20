"""Dump / patch du planned_calendar (heures_prevues des jours travail).

Dump:  .venv/bin/python -m scripts.backtest.mbc_cal MAT
Patch: .venv/bin/python -m scripts.backtest.mbc_cal MAT --set-travail-heures 4.016 [--force]
       (revert-safe : garde si tier-S baisse)
"""
from __future__ import annotations
import copy, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from app.core.database import get_supabase_admin_client
from scripts.backtest.employee_matching import match_employees, resolve_company_id
from scripts.backtest.pdf_loader import load_reference_bulletins
from scripts.backtest.backtest_company_payroll import _generate_payslip, compare_matches
from app.modules.payroll.backtest.thresholds import default_thresholds

COMPANY = "Mont Blanc Composite"
YEAR, MONTH = 2026, 5

def tier_s(m):
    _generate_payslip(m, YEAR, MONTH)
    for r in compare_matches([m], YEAR, MONTH, thresholds=default_thresholds(),
                             systemic_deltas={}, correction_attempts={}):
        return r.tier_s_max_delta
    return float("inf")

def main():
    args = sys.argv[1:]
    force = "--force" in args
    set_h = None
    if "--set-travail-heures" in args:
        set_h = float(args[args.index("--set-travail-heures")+1])
    mats = [a for a in args if not a.startswith("--")]
    # drop the value after the flag
    if set_h is not None:
        val = args[args.index("--set-travail-heures")+1]
        mats = [a for a in mats if a != val]
    admin = get_supabase_admin_client()
    refs = load_reference_bulletins(COMPANY, YEAR, MONTH)
    cid = resolve_company_id(COMPANY)
    matched = [m for m in match_employees(cid, refs).matched if m.matricule in set(mats)]
    for m in matched:
        sched = (admin.table("employee_schedules").select("id,planned_calendar")
                 .match({"employee_id": m.employee_id, "year": YEAR, "month": MONTH})
                 .maybe_single().execute())
        if not sched or not sched.data:
            print(f"{m.matricule}: pas de schedule"); continue
        planned = sched.data.get("planned_calendar") or {}
        cal = planned.get("calendrier_prevu", [])
        if set_h is None:
            from collections import Counter
            c = Counter((j.get("type"), j.get("heures_prevues")) for j in cal)
            print(f"\n== {m.matricule} == ({len(cal)} jours)")
            for (t,h),n in sorted(c.items(), key=lambda x:str(x[0])):
                print(f"   type={t} heures={h} x{n}")
            continue
        before = tier_s(m)
        snap = copy.deepcopy(planned)
        n=0
        for j in cal:
            if j.get("type") in ("travail", "conges_payes"):
                j["heures_prevues"] = set_h; n+=1
        planned["calendrier_prevu"] = cal
        admin.table("employee_schedules").update({"planned_calendar": planned}).eq("id", sched.data["id"]).execute()
        after = tier_s(m)
        if force or after < before - 0.01:
            print(f"[{m.matricule}] {before:.2f} -> {after:.2f} GARDÉ ({n} jours travail -> {set_h}h)")
        else:
            admin.table("employee_schedules").update({"planned_calendar": snap}).eq("id", sched.data["id"]).execute()
            rev = tier_s(m)
            print(f"[{m.matricule}] {before:.2f} -> essai {after:.2f} -> REVERT {rev:.2f}")

if __name__ == "__main__":
    main()
