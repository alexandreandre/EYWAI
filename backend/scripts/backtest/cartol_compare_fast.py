"""Comparaison RAPIDE Cartol sans régénération (charge payslip_data existant).

Usage: .venv/bin/python -m scripts.backtest.cartol_compare_fast --month 5
"""
from __future__ import annotations
import argparse, json
from pathlib import Path
from scripts.backtest.bulletins_source import resolve_bulletin_pdf
from scripts.backtest.employee_matching import match_employees, resolve_company_id
from scripts.backtest.pdf_loader import load_reference_bulletins
from scripts.backtest.backtest_company_payroll import compare_matches
from app.modules.payroll.backtest.thresholds import default_thresholds

SC = Path("/private/tmp/claude-501/-Users-alex-Desktop-EYWAI-EYWAI/"
          "cfdb3f75-b90e-430f-922f-effaf4ea2dbd/scratchpad")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--month", type=int, default=5)
    ap.add_argument("--year", type=int, default=2026)
    a = ap.parse_args()
    pdf = resolve_bulletin_pdf("Cartol", a.year, a.month)
    refs = load_reference_bulletins("Cartol", a.year, a.month, pdf_path=pdf)
    cid = resolve_company_id("Cartol")
    matched = match_employees(cid, refs).matched
    reps = compare_matches(matched, a.year, a.month, thresholds=default_thresholds(),
                           systemic_deltas={}, correction_attempts={})
    out = {r.matricule: round(r.tier_s_max_delta, 2) for r in reps}
    (SC / f"cartol_fast_{a.month:02d}.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    conv = sum(1 for v in out.values() if v <= 0.05)
    u1 = sum(1 for v in out.values() if v <= 1.0)
    u20 = sum(1 for v in out.values() if v <= 20.0)
    print(f"=== Cartol {a.month:02d}/{a.year} (compare-only, état DB actuel) ===")
    print(f"  ≤0.05€ : {conv}/{len(out)}   ≤1€ : {u1}/{len(out)}   ≤20€ : {u20}/{len(out)}")
    print("  --- 30 plus proches ---")
    for mat, v in sorted(out.items(), key=lambda x: x[1])[:30]:
        print(f"    {mat:14s} {v:9.2f}")


if __name__ == "__main__":
    main()
