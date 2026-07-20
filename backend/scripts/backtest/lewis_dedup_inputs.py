"""Lewis mai 2026 - supprime les monthly_inputs DUPLIQUES (meme nom + meme
montant insere deux fois lors de l'import DSN) pour un salarie donne.
Revert-safe (garde si tier-S baisse strictement), UN SALARIE A LA FOIS.

Usage : .venv/bin/python -m scripts.backtest.lewis_dedup_inputs MATRICULE
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

COMPANY = "Lewis"
YEAR, MONTH = 2026, 5


def tier_s(m):
    _generate_payslip(m, YEAR, MONTH)
    for r in compare_matches([m], YEAR, MONTH, thresholds=default_thresholds(),
                              systemic_deltas={}, correction_attempts={}):
        return r.tier_s_max_delta
    return float("inf")


def main():
    matricule = sys.argv[1]
    admin = get_supabase_admin_client()
    refs = load_reference_bulletins(COMPANY, YEAR, MONTH)
    cid = resolve_company_id(COMPANY)
    m = next(x for x in match_employees(cid, refs).matched if x.matricule == matricule)

    rows = (
        admin.table("monthly_inputs").select("*")
        .match({"employee_id": m.employee_id, "year": YEAR, "month": MONTH})
        .execute().data
    ) or []
    snap = copy.deepcopy(rows)

    seen = {}
    to_delete_ids = []
    for r in rows:
        key = (r.get("name"), r.get("amount"))
        if key in seen:
            to_delete_ids.append(r["id"])
        else:
            seen[key] = r["id"]

    if not to_delete_ids:
        print(f"[{matricule}] aucun doublon detecte")
        return

    before = tier_s(m)
    for rid in to_delete_ids:
        admin.table("monthly_inputs").delete().eq("id", rid).execute()

    after = tier_s(m)
    keep = after < before - 0.01
    if keep:
        print(f"[{matricule}] {len(to_delete_ids)} doublon(s) supprime(s) : {before:.2f} -> {after:.2f}  GARDE")
    else:
        # revert : ré-insère les lignes supprimées telles quelles
        for r in snap:
            if r["id"] in to_delete_ids:
                payload = {k: v for k, v in r.items() if k != "id"}
                admin.table("monthly_inputs").insert(payload).execute()
        _generate_payslip(m, YEAR, MONTH)
        print(f"[{matricule}] {len(to_delete_ids)} doublon(s) essaye(s) : {before:.2f} -> {after:.2f}  REVERT")


if __name__ == "__main__":
    main()
