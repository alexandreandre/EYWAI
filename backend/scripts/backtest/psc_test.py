"""Test revert-safe : pour un matricule, bascule part_patronale_soumise_a_csg
de sa mutuelle à False, régénère, imprime les 5 champs tier-S avant/après, puis
RESTAURE."""
from __future__ import annotations
import sys, copy
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from app.core.database import get_supabase_admin_client
from scripts.backtest.employee_matching import match_employees, resolve_company_id
from scripts.backtest.pdf_loader import load_reference_bulletins
from scripts.backtest.backtest_company_payroll import _generate_payslip

COMPANY, YEAR, MONTH = "Mont Blanc Composite", 2026, 5

def snap(m, admin):
    _generate_payslip(m, YEAR, MONTH)
    ps = admin.table("payslips").select("payslip_data").match(
        {"employee_id": m.employee_id, "year": YEAR, "month": MONTH}
    ).maybe_single().execute().data["payslip_data"]
    sn = ps.get("synthese_net") or {}
    r = m.reference
    return {
        "brut": (ps.get("salaire_brut"), r.salaire_brut),
        "NI": (sn.get("net_imposable"), r.net_imposable),
        "MNS": (sn.get("montant_net_social"), r.montant_net_social),
        "net": (ps.get("net_a_payer"), r.net_a_payer),
    }

def show(tag, d):
    print(tag)
    for k, (ev, rv) in d.items():
        delta = (ev - rv) if ev is not None and rv is not None else None
        print(f"   {k:5s} EYWAI={ev} REAL={rv} delta={delta}")

def main():
    admin = get_supabase_admin_client()
    refs = load_reference_bulletins(COMPANY, YEAR, MONTH)
    cid = resolve_company_id(COMPANY)
    matched = match_employees(cid, refs).matched
    mat = sys.argv[1]
    m = [x for x in matched if x.matricule == mat][0]
    sp = admin.table("employees").select("specificites_paie").eq("id", m.employee_id).single().execute().data["specificites_paie"]
    mut_ids = ((sp or {}).get("mutuelle") or {}).get("mutuelle_type_ids") or []
    print("mutuelle_type_ids:", mut_ids)
    types = admin.table("company_mutuelle_types").select("*").in_("id", mut_ids).execute().data or []
    baks = {t["id"]: t.get("part_patronale_soumise_a_csg") for t in types}
    for t in types:
        print("  type", t["id"], "libelle", t.get("libelle"), "sal", t.get("montant_salarial"), "pat", t.get("montant_patronal"), "soumise_csg", t.get("part_patronale_soumise_a_csg"))
    before = snap(m, admin)
    show("=== AVANT ===", before)
    for tid in mut_ids:
        admin.table("company_mutuelle_types").update({"part_patronale_soumise_a_csg": False}).eq("id", tid).execute()
    try:
        after = snap(m, admin)
        show("=== APRÈS (soumise_csg=False) ===", after)
    finally:
        for tid, val in baks.items():
            admin.table("company_mutuelle_types").update({"part_patronale_soumise_a_csg": val}).eq("id", tid).execute()
        _generate_payslip(m, YEAR, MONTH)
        print("restauré")

if __name__ == "__main__":
    main()
