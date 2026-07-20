#!/usr/bin/env python3
"""Verification finale complete Colorplast jan-juin : setup (bases historiques
+ inputs) puis compare, mois par mois, avec restauration backup avant mai/juin.
Laisse la DB au backup a la fin."""
from __future__ import annotations

import json
from app.core.database import get_supabase_admin_client, supabase
from scripts.backtest.employee_matching import resolve_company_id, match_employees
from scripts.backtest.pdf_loader import load_reference_bulletins
from scripts.backtest.bulletins_source import resolve_bulletin_pdf
from app.modules.payroll.backtest.comparator import compare_bulletins
from app.modules.payroll.backtest.thresholds import default_thresholds
from app.modules.payroll.documents.payslip_generator import process_payslip_generation
from scripts.backtest import colorplast_setup as CS

BACKUP = "/private/tmp/claude-501/-Users-alex-Desktop-EYWAI-EYWAI/cfdb3f75-b90e-430f-922f-effaf4ea2dbd/scratchpad/full_backup.json"


def restore(admin):
    b = json.load(open(BACKUP))
    for m, v in b.items():
        admin.table("employees").update(
            {"salaire_de_base": v["salaire_de_base"], "specificites_paie": v["specificites_paie"]}
        ).eq("id", v["id"]).execute()


def compare_month(company, year, month):
    pdf = resolve_bulletin_pdf(company, year, month)
    refs = load_reference_bulletins(company, year, month, pdf_path=pdf)
    cid = resolve_company_id(company)
    matching = match_employees(cid, refs)
    th = default_thresholds()
    rows = []
    for m in matching.matched:
        if not m.reference:
            continue
        process_payslip_generation(m.employee_id, year, month)
        ps = supabase.table("payslips").select("payslip_data").match(
            {"employee_id": m.employee_id, "year": year, "month": month}).maybe_single().execute()
        pd = ps.data["payslip_data"] if ps and ps.data else {}
        rep = compare_bulletins(pd, m.reference, employee_id=m.employee_id, thresholds=th)
        rows.append((m.matricule, rep.tier_s_max_delta))
    rows.sort(key=lambda x: x[1])
    conv = sum(1 for _, d in rows if d <= 0.05)
    print(f"===== MONTH {month} : {conv}/{len(rows)} convergés (<=0.05) =====")
    for mat, d in rows:
        flag = "OK" if d <= 0.05 else ("~ " if d <= 20 else "XX")
        print(f"  {flag} {mat:12} {d:8.2f}")
    return conv, len(rows)


def main():
    admin = get_supabase_admin_client()
    company, year = "Colorplast", 2026
    summary = {}
    for month in (1, 2, 3, 4):
        CS.apply_month(company, year, month)
        summary[month] = compare_month(company, year, month)
    restore(admin)
    summary[5] = compare_month(company, year, 5)
    restore(admin)
    CS.apply_month(company, year, 6)
    summary[6] = compare_month(company, year, 6)
    restore(admin)
    print("\n==== RÉCAP ====")
    for m in sorted(summary):
        c, t = summary[m]
        print(f"  Mois {m}: {c}/{t}")
    print("[DB restaurée au backup]")


if __name__ == "__main__":
    main()
