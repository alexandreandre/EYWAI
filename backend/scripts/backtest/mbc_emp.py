"""Inspecte le record employé (contrat, salaire, classification) + monthly_inputs.

Usage: .venv/bin/python -m scripts.backtest.mbc_emp MATRICULE [MATRICULE ...]
"""
from __future__ import annotations
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from app.core.database import get_supabase_admin_client
from scripts.backtest.employee_matching import match_employees, resolve_company_id
from scripts.backtest.pdf_loader import load_reference_bulletins

COMPANY = "Mont Blanc Composite"
YEAR, MONTH = 2026, 5

def main():
    admin = get_supabase_admin_client()
    refs = load_reference_bulletins(COMPANY, YEAR, MONTH)
    cid = resolve_company_id(COMPANY)
    matched = match_employees(cid, refs).matched
    wanted = set(a for a in sys.argv[1:] if not a.startswith("--"))
    matched = [m for m in matched if m.matricule in wanted]
    for m in matched:
        emp = admin.table("employees").select("*").eq("id", m.employee_id).single().execute().data
        print(f"\n===== {m.matricule} ({m.first_name} {m.last_name}) id={m.employee_id} =====")
        for k in sorted(emp):
            v = emp[k]
            if k in ("specificites_paie",):
                print(f"  {k} = {json.dumps(v, ensure_ascii=False)}")
            elif isinstance(v, (dict, list)):
                print(f"  {k} = {json.dumps(v, ensure_ascii=False)[:300]}")
            else:
                print(f"  {k} = {v}")
        mi = (admin.table("monthly_inputs").select("*")
              .match({"employee_id": m.employee_id, "year": YEAR, "month": MONTH}).execute().data) or []
        print(f"  -- monthly_inputs ({len(mi)}) --")
        for r in mi:
            print(f"     name={r.get('name')!r} amount={r.get('amount')} taxed={r.get('is_socially_taxed')} taxable={r.get('is_taxable')} qty={r.get('payroll_quantity')}")

if __name__ == "__main__":
    main()
