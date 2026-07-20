"""Test revert-safe : pour chaque matricule, vide actual_hours.calendrier_reel,
régénère, imprime le brut/tierS et les absences résiduelles, puis RESTAURE.
"""
from __future__ import annotations
import sys, copy
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from app.core.database import get_supabase_admin_client
from scripts.backtest.employee_matching import match_employees, resolve_company_id
from scripts.backtest.pdf_loader import load_reference_bulletins
from scripts.backtest.backtest_company_payroll import _generate_payslip, compare_matches
from app.modules.payroll.backtest.thresholds import default_thresholds

COMPANY, YEAR, MONTH = "Mont Blanc Composite", 2026, 5

def tier_s(m):
    _generate_payslip(m, YEAR, MONTH)
    for r in compare_matches([m], YEAR, MONTH, thresholds=default_thresholds(), systemic_deltas={}, correction_attempts={}):
        return r
    return None

def main():
    admin = get_supabase_admin_client()
    refs = load_reference_bulletins(COMPANY, YEAR, MONTH)
    cid = resolve_company_id(COMPANY)
    matched = match_employees(cid, refs).matched
    wanted = set(sys.argv[1:])
    for m in matched:
        if wanted and m.matricule not in wanted:
            continue
        row = (admin.table("employee_schedules").select("id,actual_hours")
               .match({"employee_id": m.employee_id, "year": YEAR, "month": MONTH})
               .maybe_single().execute())
        if not row or not row.data:
            print(f"{m.matricule}: pas de schedule"); continue
        sid = row.data["id"]; ah = row.data.get("actual_hours") or {}
        bak = copy.deepcopy(ah)
        before = tier_s(m)
        ah2 = copy.deepcopy(ah); ah2["calendrier_reel"] = []
        admin.table("employee_schedules").update({"actual_hours": ah2}).eq("id", sid).execute()
        try:
            after = tier_s(m)
            ps = (admin.table("payslips").select("payslip_data")
                  .match({"employee_id": m.employee_id, "year": YEAR, "month": MONTH})
                  .maybe_single().execute().data["payslip_data"])
            abss = [(l["libelle"][:24], l.get("perte")) for l in (ps.get("details_absences") or [])]
            print(f"{m.matricule:12s} tierS {before.tier_s_max_delta:8.2f} -> {after.tier_s_max_delta:8.2f}  brut={ps.get('salaire_brut')} residualAbs={abss}", flush=True)
        finally:
            admin.table("employee_schedules").update({"actual_hours": bak}).eq("id", sid).execute()
            _generate_payslip(m, YEAR, MONTH)  # regen to restore payslip too

if __name__ == "__main__":
    main()
