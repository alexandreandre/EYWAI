"""Applique un patch employé ponctuel, revert-safe (garde si tier-S baisse).

Le patch est un dict Python passé en littéral JSON via --patch, structure :
{
  "salaire_de_base": {"type": "mensuel", "valeur": 1922.36},   # optionnel, remplace
  "seniority_reference_date": "2021-01-01",                     # optionnel
  "specificites_paie": { ... merge shallow ... },               # optionnel, merge
  "add_inputs": [                                               # optionnel, insère
     {"name": "Prime ancienneté", "amount": 50.25, "taxed": true, "taxable": true,
      "qty": null}
  ],
  "del_input_names": ["..."]                                    # optionnel, supprime par name
}

Usage:
  .venv/bin/python -m scripts.backtest.mbc_try MATRICULE --patch '<json>'
  .venv/bin/python -m scripts.backtest.mbc_try MATRICULE --patch-file /path.json
  ajouter --force pour garder même sans amélioration (déconseillé).
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
CONV = 0.05


def tier_s(match):
    _generate_payslip(match, YEAR, MONTH)
    for r in compare_matches([match], YEAR, MONTH, thresholds=default_thresholds(),
                             systemic_deltas={}, correction_attempts={}):
        return r.tier_s_max_delta
    return float("inf")


def main():
    args = sys.argv[1:]
    force = "--force" in args
    patch = None
    mats = []
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--force":
            i += 1
        elif a == "--patch":
            patch = json.loads(args[i + 1]); i += 2
        elif a == "--patch-file":
            patch = json.loads(Path(args[i + 1]).read_text()); i += 2
        else:
            mats.append(a); i += 1
    wanted = set(mats)
    admin = get_supabase_admin_client()
    refs = load_reference_bulletins(COMPANY, YEAR, MONTH)
    cid = resolve_company_id(COMPANY)
    matched = [m for m in match_employees(cid, refs).matched if m.matricule in wanted]
    if not matched:
        print("Aucun matricule:", wanted); return

    for m in matched:
        eid = m.employee_id
        before = tier_s(m)
        # snapshot
        emp = admin.table("employees").select(
            "salaire_de_base,seniority_reference_date,specificites_paie"
        ).eq("id", eid).single().execute().data
        snap_emp = copy.deepcopy(emp)
        snap_inputs = copy.deepcopy(
            (admin.table("monthly_inputs").select("*")
             .match({"employee_id": eid, "year": YEAR, "month": MONTH}).execute().data) or [])
        # apply
        upd = {}
        if "salaire_de_base" in patch:
            upd["salaire_de_base"] = patch["salaire_de_base"]
        if "seniority_reference_date" in patch:
            upd["seniority_reference_date"] = patch["seniority_reference_date"]
        if "specificites_paie" in patch:
            sp = copy.deepcopy(emp.get("specificites_paie") or {})
            sp.update(patch["specificites_paie"])
            upd["specificites_paie"] = sp
        if upd:
            admin.table("employees").update(upd).eq("id", eid).execute()
        for nm in patch.get("del_input_names", []):
            admin.table("monthly_inputs").delete().match(
                {"employee_id": eid, "year": YEAR, "month": MONTH, "name": nm}).execute()
        for ai in patch.get("add_inputs", []):
            row = {"employee_id": eid, "company_id": cid, "year": YEAR, "month": MONTH,
                   "name": ai["name"], "amount": ai["amount"],
                   "is_socially_taxed": ai.get("taxed", True),
                   "is_taxable": ai.get("taxable", True)}
            if ai.get("qty") is not None:
                row["payroll_quantity"] = ai["qty"]
            admin.table("monthly_inputs").insert(row).execute()

        after = tier_s(m)
        keep = force or after < before - 0.01
        if keep:
            print(f"[{m.matricule}] {before:.2f} -> {after:.2f}  GARDÉ")
        else:
            # revert
            admin.table("employees").update({
                "salaire_de_base": snap_emp.get("salaire_de_base"),
                "seniority_reference_date": snap_emp.get("seniority_reference_date"),
                "specificites_paie": snap_emp.get("specificites_paie"),
            }).eq("id", eid).execute()
            admin.table("monthly_inputs").delete().match(
                {"employee_id": eid, "year": YEAR, "month": MONTH}).execute()
            cols = ("name", "description", "amount", "is_socially_taxed", "is_taxable",
                    "payroll_quantity", "catalog_prime_id", "export_code", "bonus_type_id",
                    "participation_campaign_id", "participation_bulletin_id")
            for row in snap_inputs:
                payload = {k: row.get(k) for k in cols if k in row}
                payload.update({"employee_id": eid, "company_id": cid, "year": YEAR, "month": MONTH})
                admin.table("monthly_inputs").insert(payload).execute()
            reverted = tier_s(m)
            print(f"[{m.matricule}] {before:.2f} -> essai {after:.2f} -> REVERT {reverted:.2f}")


if __name__ == "__main__":
    main()
