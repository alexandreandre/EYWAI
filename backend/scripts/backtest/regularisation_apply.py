"""Applique une liste de régularisations antérieures (planned_calendar
.regularisations_anterieures) sur le mois COURANT d'un salarié, revert-safe
(garde si tier-S baisse strictement, sinon revert).

Chantier 3 (fondation cross-mois) — cf. mémoire backtest-paie.

Usage:
  .venv/bin/python -m scripts.backtest.regularisation_apply MAT --entries '[
      {"date_complete": "2026-04-27", "type": "absence_non_remuneree", "heures": 7.0}
  ]' [--force]
"""
from __future__ import annotations
import copy, json, sys
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


def diag(m):
    _generate_payslip(m, YEAR, MONTH)
    for r in compare_matches([m], YEAR, MONTH, thresholds=default_thresholds(),
                              systemic_deltas={}, correction_attempts={}):
        print(f"  tierS={r.tier_s_max_delta:.2f}")
        for ln in r.lines:
            if abs(ln.delta or 0.0) > 0.005:
                print(f"    {ln.field_key}: eywai={ln.actual_value} ref={ln.reference_value} delta={ln.delta}")
        return r.tier_s_max_delta
    return float("inf")


def main():
    args = sys.argv[1:]
    force = "--force" in args
    entries = None
    if "--entries" in args:
        entries = json.loads(args[args.index("--entries") + 1])
    mats = [a for a in args if not a.startswith("--") and a != json.dumps(entries)]
    # drop the raw json literal from mats if present
    mats = [a for a in mats if not a.startswith("[")]

    admin = get_supabase_admin_client()
    refs = load_reference_bulletins(COMPANY, YEAR, MONTH)
    cid = resolve_company_id(COMPANY)
    matched = [m for m in match_employees(cid, refs).matched if m.matricule in set(mats)]
    if not matched:
        print("Aucun matricule:", mats)
        return

    for m in matched:
        sched = (
            admin.table("employee_schedules")
            .select("id,planned_calendar")
            .match({"employee_id": m.employee_id, "year": YEAR, "month": MONTH})
            .maybe_single()
            .execute()
        )
        if not sched or not sched.data:
            print(f"{m.matricule}: pas de schedule pour {MONTH}/{YEAR}")
            continue

        before = tier_s(m)
        planned = sched.data.get("planned_calendar") or {}
        snap_planned = copy.deepcopy(planned)

        new_planned = copy.deepcopy(planned)
        new_planned["regularisations_anterieures"] = entries
        admin.table("employee_schedules").update(
            {"planned_calendar": new_planned}
        ).eq("id", sched.data["id"]).execute()

        print(f"[{m.matricule}] APRÈS application (avant décision revert):")
        after = diag(m)
        keep = force or after < before - 0.01
        if keep:
            print(f"[{m.matricule}] {before:.2f} -> {after:.2f}  GARDÉ")
        else:
            admin.table("employee_schedules").update(
                {"planned_calendar": snap_planned}
            ).eq("id", sched.data["id"]).execute()
            _generate_payslip(m, YEAR, MONTH)
            print(f"[{m.matricule}] {before:.2f} -> {after:.2f}  REVERT (pas d'amélioration)")


if __name__ == "__main__":
    main()
