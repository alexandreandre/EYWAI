#!/usr/bin/env python3
"""Verification finale complete Colorplast jan-juin : setup (bases historiques
+ inputs) puis compare, mois par mois, avec restauration backup avant mai/juin.
Laisse la DB au backup a la fin."""
from __future__ import annotations

import json
import os
from app.core.database import get_supabase_admin_client, supabase
from scripts.backtest.employee_matching import resolve_company_id, match_employees
from scripts.backtest.pdf_loader import load_reference_bulletins
from scripts.backtest.bulletins_source import resolve_bulletin_pdf
from app.modules.payroll.backtest.comparator import compare_bulletins
from app.modules.payroll.backtest.thresholds import default_thresholds
from app.modules.payroll.documents.payslip_generator import process_payslip_generation
from scripts.backtest import colorplast_setup as CS

# Le backup vivait dans le scratchpad d'une session (chemin en dur, effacé
# depuis). Le 02/08/2026, restore() a levé FileNotFoundError APRÈS avoir
# appliqué janvier→avril : cinq salariés Colorplast sont restés avec leur
# salaire de base d'avant l'augmentation de mai. Le backup est désormais
# versionné et créé automatiquement avant toute écriture.
BACKUP = os.path.join(os.path.dirname(__file__), "_colorplast_backup", "employees.json")


def dump_backup(admin) -> None:
    """Photographie l'état production. Ne réécrit jamais un backup existant."""
    if os.path.exists(BACKUP):
        return
    os.makedirs(os.path.dirname(BACKUP), exist_ok=True)
    company_id = resolve_company_id("Colorplast")
    rows = (
        supabase.table("employees")
        .select("id, last_name, salaire_de_base, specificites_paie")
        .eq("company_id", company_id)
        .execute()
        .data
        or []
    )
    with open(BACKUP, "w", encoding="utf-8") as fh:
        json.dump({r["last_name"]: r for r in rows}, fh, ensure_ascii=False, indent=2)
    print(f"[backup créé] {BACKUP} ({len(rows)} salariés)")


def restore(admin):
    if not os.path.exists(BACKUP):
        raise SystemExit(
            f"ABANDON : backup introuvable ({BACKUP}). Restaurer sans référence "
            "laisserait la production avec les valeurs de backtest."
        )
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
    # Avant toute écriture : la photo de l'état production doit exister.
    dump_backup(admin)
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
