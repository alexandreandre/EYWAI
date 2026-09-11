#!/usr/bin/env python3
"""Relevé des bulletins d'une base (test par défaut) : une ligne CSV par bulletin
avec les cinq figures comparées aux bulletins du cabinet.

Prévu pour le workflow « Script sur l'env de test » (lecture seule, `--apply`
ignoré) ; le journal du run se compare ensuite en local avec
`scripts/backtest/compare_dump_to_references.py`.

Colonnes : societe;matricule;annee;mois;statut;brut;net_imposable;mns;net_a_payer;pas
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import supabase  # noqa: E402

YEAR = 2026


def main() -> None:
    companies = {c["id"]: c["company_name"] for c in supabase.table("companies").select("id, company_name").execute().data}
    employees = {e["id"]: e.get("matricule") or e.get("last_name") for e in
                 supabase.table("employees").select("id, matricule, last_name").execute().data}
    rows = (supabase.table("payslips")
            .select("company_id, employee_id, year, month, status, payslip_data")
            .eq("year", YEAR).execute().data)
    print("DUMP_BEGIN")
    print("societe;matricule;annee;mois;statut;brut;net_imposable;mns;net_a_payer;pas")
    for r in sorted(rows, key=lambda r: (companies.get(r["company_id"], ""), r["month"], employees.get(r["employee_id"], ""))):
        d = r.get("payslip_data") or {}
        syn = d.get("synthese_net") or {}
        pas = (syn.get("impot_prelevement_a_la_source") or {}).get("montant")
        vals = [d.get("salaire_brut"), syn.get("net_imposable"), syn.get("montant_net_social"), d.get("net_a_payer"), pas]
        print(";".join([companies.get(r["company_id"], "?"), str(employees.get(r["employee_id"], "?")), str(r["year"]),
                        str(r["month"]), str(r.get("status") or "")] + ["" if v is None else f"{float(v):.2f}" for v in vals]))
    print("DUMP_END")
    print(f"{len(rows)} bulletins relevés.", file=sys.stderr)


if __name__ == "__main__":
    main()
