#!/usr/bin/env python3
"""Harnais de comparaison Colorplast (backtest jan-juin 2026).

Pour un mois donne : matche les employes aux bulletins de reference (PDF du
dossier Bulletins/), (re)genere les bulletins EYWAI, compare les figures cles
tier S salarie par salarie et affiche un tableau lisible.

Usage:
    .venv/bin/python -m scripts.backtest.colorplast_compare --month 1
    .venv/bin/python -m scripts.backtest.colorplast_compare --month 1 --no-regen
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.database import supabase
from app.modules.payroll.backtest.comparator import compare_bulletins
from app.modules.payroll.backtest.thresholds import default_thresholds
from scripts.backtest.bulletins_source import resolve_bulletin_pdf
from scripts.backtest.employee_matching import match_employees, resolve_company_id
from scripts.backtest.pdf_loader import load_reference_bulletins

TIER_S = ["salaire_brut", "net_imposable", "montant_net_social", "net_avant_impot",
          "net_a_payer", "pas_montant"]


def _generate(match, year: int, month: int) -> Optional[str]:
    try:
        if match.is_forfait_jour:
            from app.modules.payroll.documents.payslip_generator_forfait import (
                process_payslip_generation_forfait as gen,
            )
        else:
            from app.modules.payroll.documents.payslip_generator import (
                process_payslip_generation as gen,
            )
        gen(match.employee_id, year, month)
        return None
    except Exception as exc:  # noqa: BLE001
        return f"{type(exc).__name__}: {exc}"


def _load_payslip(employee_id: str, year: int, month: int) -> Dict[str, Any]:
    res = (
        supabase.table("payslips")
        .select("payslip_data")
        .match({"employee_id": employee_id, "year": year, "month": month})
        .maybe_single()
        .execute()
    )
    if not res or not res.data:
        return {}
    return res.data.get("payslip_data") or {}


def run(company: str, year: int, month: int, regen: bool = True) -> Dict[str, float]:
    thresholds = default_thresholds()
    pdf = resolve_bulletin_pdf(company, year, month)
    references = load_reference_bulletins(company, year, month, pdf_path=pdf)
    company_id = resolve_company_id(company)
    matching = match_employees(company_id, references)

    print(f"=== {company} {month:02d}/{year} ===")
    print(f"PDF: {pdf.name}")
    print(f"Refs parsees: {len(references)} | matches: {len(matching.matched)} | "
          f"refs orphelines: {len(matching.unmatched_references)} | "
          f"employes sans ref: {len(matching.unmatched_employees)}")
    if matching.unmatched_references:
        print("  refs orphelines:", [getattr(r, 'matricule', '?') for r in matching.unmatched_references])

    if regen:
        for m in matching.matched:
            err = _generate(m, year, month)
            if err:
                print(f"  GEN ERROR {m.matricule}: {err}")

    results: Dict[str, float] = {}
    rows = []
    for m in matching.matched:
        if not m.reference:
            continue
        pdata = _load_payslip(m.employee_id, year, month)
        rep = compare_bulletins(
            pdata, m.reference,
            employee_id=m.employee_id,
            employee_name=f"{m.first_name} {m.last_name}",
            thresholds=thresholds,
        )
        results[m.matricule] = rep.tier_s_max_delta
        # detail per tier S field
        detail = {ln.field_key: (ln.reference_value, ln.actual_value, ln.delta)
                  for ln in rep.lines if ln.tier == "S"}
        rows.append((m.matricule, rep.tier_s_max_delta, detail))

    rows.sort(key=lambda x: x[1])
    print()
    print(f"{'MATRICULE':<12} {'tierS_max':>10}  worst fields")
    for mat, tsmax, detail in rows:
        worst = sorted(detail.items(), key=lambda kv: -abs(kv[1][2]))[:3]
        worst_s = "  ".join(
            f"{k}:{v[2]:+.2f}(ref{v[0] if v[0] is None else round(v[0],2)}/eywai{v[1] if v[1] is None else round(v[1],2)})"
            for k, v in worst if abs(v[2]) > 0.005
        )
        flag = "OK " if tsmax <= 0.05 else ("~  " if tsmax <= 20 else "XX ")
        print(f"{flag}{mat:<12} {tsmax:>10.2f}  {worst_s}")

    converged = sum(1 for v in results.values() if v <= 0.05)
    print(f"\nCONVERGES tier S (<=0.05): {converged}/{len(results)}")
    return results


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--company", default="Colorplast")
    ap.add_argument("--year", type=int, default=2026)
    ap.add_argument("--month", type=int, required=True)
    ap.add_argument("--no-regen", action="store_true")
    args = ap.parse_args()
    run(args.company, args.year, args.month, regen=not args.no_regen)


if __name__ == "__main__":
    main()
