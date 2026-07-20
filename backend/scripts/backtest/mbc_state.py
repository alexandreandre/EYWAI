"""Snapshot d'état MBC mai 2026 : régénère (optionnel) + compare tous les
matchés, imprime le tier-S trié avec le détail des lignes tier-S divergentes.

Usage (depuis backend/) :
    .venv/bin/python -m scripts.backtest.mbc_state [--no-regen] [MATRICULE ...]
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.backtest.employee_matching import match_employees, resolve_company_id
from scripts.backtest.pdf_loader import load_reference_bulletins
from scripts.backtest.backtest_company_payroll import _generate_payslip, compare_matches
from app.modules.payroll.backtest.thresholds import default_thresholds

COMPANY = "Mont Blanc Composite"
YEAR, MONTH = 2026, 5

TIER_S_KEYS = {"salaire_brut", "net_imposable", "montant_net_social",
               "net_a_payer", "pas_montant"}


def main():
    args = sys.argv[1:]
    regen = "--no-regen" not in args
    company = COMPANY
    if "--company" in args:
        i = args.index("--company")
        company = args[i + 1]
        args = args[:i] + args[i + 2:]
    wanted = set(a for a in args if not a.startswith("--"))

    refs = load_reference_bulletins(company, YEAR, MONTH)
    cid = resolve_company_id(company)
    matched = match_employees(cid, refs).matched
    if wanted:
        matched = [m for m in matched if m.matricule in wanted]

    if regen:
        for m in matched:
            try:
                _generate_payslip(m, YEAR, MONTH)
            except Exception as exc:
                print(f"[GEN ERR {m.matricule}] {exc}", flush=True)

    reports = compare_matches(matched, YEAR, MONTH, thresholds=default_thresholds(),
                              systemic_deltas={}, correction_attempts={})
    reports.sort(key=lambda r: r.tier_s_max_delta)

    n_conv = 0
    for r in reports:
        d = r.tier_s_max_delta
        if d <= 0.05:
            n_conv += 1
        flag = "OK " if d <= 0.05 else "   "
        detail = []
        for ln in r.lines:
            if ln.tier == "S" and abs(ln.delta) > 0.05:
                detail.append(f"{ln.field_key}={ln.delta:+.2f}(ref {ln.reference_value} vs {ln.actual_value})")
        print(f"{flag}[{r.matricule:14s}] tierS={d:8.2f}  {r.employee_name}", flush=True)
        for dd in detail:
            print(f"        {dd}", flush=True)

    print(f"\n=== {n_conv}/{len(reports)} convergés (≤0,05€) ===", flush=True)


if __name__ == "__main__":
    main()
