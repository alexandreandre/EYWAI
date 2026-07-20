"""Applique part_patronale_reintegree_impot=False aux salariés dont le résiduel
net_imposable = leur part patronale mutuelle famille (non réintégrée par Cegid).
Revert-safe : garde si le tier-S s'améliore, sinon restaure."""
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
        return r.tier_s_max_delta
    return float("inf")

def main():
    admin = get_supabase_admin_client()
    refs = load_reference_bulletins(COMPANY, YEAR, MONTH)
    cid = resolve_company_id(COMPANY)
    matched = match_employees(cid, refs).matched
    for mat in sys.argv[1:]:
        m = [x for x in matched if x.matricule == mat]
        if not m:
            print(f"{mat}: non matché"); continue
        m = m[0]
        emp = admin.table("employees").select("specificites_paie").eq("id", m.employee_id).single().execute().data
        sp = emp["specificites_paie"] or {}
        if not (sp.get("mutuelle") or {}).get("adhesion"):
            print(f"{mat}: pas de mutuelle"); continue
        bak = copy.deepcopy(sp)
        before = tier_s(m)
        sp.setdefault("mutuelle", {})["part_patronale_reintegree_impot"] = False
        admin.table("employees").update({"specificites_paie": sp}).eq("id", m.employee_id).execute()
        after = tier_s(m)
        if after < before - 0.01:
            print(f"{mat:12s} {before:8.2f} -> {after:8.2f}  GARDÉ")
        else:
            admin.table("employees").update({"specificites_paie": bak}).eq("id", m.employee_id).execute()
            _generate_payslip(m, YEAR, MONTH)
            print(f"{mat:12s} {before:8.2f} -> {after:8.2f}  revert")

if __name__ == "__main__":
    main()
