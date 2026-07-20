#!/usr/bin/env python3
"""Verification finale Comitech jan-juin : applique le setup mois par mois,
compare, imprime le recap tier S, puis restaure la DB au backup (configs +
seniority) et purge les monthly_inputs BACKTEST_AUTO_COMITECH.
"""
from __future__ import annotations
import json
from app.core.database import get_supabase_admin_client, supabase
from scripts.backtest.employee_matching import resolve_company_id, match_employees
from scripts.backtest.pdf_loader import load_reference_bulletins
from scripts.backtest.bulletins_source import resolve_bulletin_pdf
from app.modules.payroll.backtest.comparator import compare_bulletins
from app.modules.payroll.backtest.thresholds import default_thresholds
from scripts.backtest import comitech_setup as CS

BACKUP = ("/private/tmp/claude-501/-Users-alex-Desktop-EYWAI-EYWAI/"
          "cfdb3f75-b90e-430f-922f-effaf4ea2dbd/scratchpad/comitech_backup.json")
COMPANY = "Comitech Composite"


def _gen(match, year, month):
    try:
        if match.is_forfait_jour:
            from app.modules.payroll.documents.payslip_generator_forfait import (
                process_payslip_generation_forfait as g)
        else:
            from app.modules.payroll.documents.payslip_generator import (
                process_payslip_generation as g)
        g(match.employee_id, year, month)
    except Exception:
        pass


def compare_month(year, month):
    pdf = resolve_bulletin_pdf(COMPANY, year, month)
    refs = load_reference_bulletins(COMPANY, year, month, pdf_path=pdf)
    cid = resolve_company_id(COMPANY)
    matching = match_employees(cid, refs)
    th = default_thresholds()
    rows = []
    for m in matching.matched:
        if not m.reference:
            continue
        _gen(m, year, month)
        ps = supabase.table("payslips").select("payslip_data").match(
            {"employee_id": m.employee_id, "year": year, "month": month}).maybe_single().execute()
        pd = ps.data["payslip_data"] if ps and ps.data else {}
        rep = compare_bulletins(pd, m.reference, employee_id=m.employee_id, thresholds=th)
        rows.append((m.matricule, rep.tier_s_max_delta))
    rows.sort(key=lambda x: x[1])
    conv = sum(1 for _, d in rows if d <= 0.05)
    near = sum(1 for _, d in rows if d <= 20)
    print(f"===== MOIS {month} : {conv}/{len(rows)} convergés (<=0.05), {near}/{len(rows)} sous 20€ =====")
    for mat, d in rows:
        flag = "OK" if d <= 0.05 else ("~ " if d <= 20 else "XX")
        print(f"  {flag} {mat:12} {d:10.2f}")
    return conv, len(rows)


def restore():
    admin = get_supabase_admin_client()
    b = json.load(open(BACKUP))
    cid = resolve_company_id(COMPANY)
    for mat, v in b.items():
        admin.table("employees").update({
            "salaire_de_base": v["salaire_de_base"],
            "specificites_paie": v["specificites_paie"],
            "seniority_reference_date": None,
        }).eq("id", v["id"]).execute()
    # purge monthly_inputs backtest
    emp_ids = [v["id"] for v in b.values()]
    for eid in emp_ids:
        admin.table("monthly_inputs").delete().eq("employee_id", eid).like(
            "description", f"%{CS.MARKER}%").execute()
    print("[DB restaurée : configs + seniority=None + purge monthly_inputs BACKTEST]")


def main():
    summary = {}
    for month in (1, 2, 3, 4, 5, 6):
        CS.apply_month(COMPANY, 2026, month)
        summary[month] = compare_month(2026, month)
    print("\n==== RÉCAP COMITECH ====")
    for m in sorted(summary):
        c, t = summary[m]
        print(f"  Mois {m}: {c}/{t}")
    restore()


if __name__ == "__main__":
    main()
