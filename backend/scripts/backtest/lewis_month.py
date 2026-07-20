"""Comparateur backtest paie paramétrable (company/year/month) — dérivé de
`mbc_state.py`, mais résout le PDF bulletin réel via `bulletins_source` (dossier
`Bulletins/BULLETIN <NOM> 01 02 03 04 05 06/`) pour n'importe quel mois.

Usage (depuis backend/) :
    .venv/bin/python -m scripts.backtest.lewis_month <Company> <year> <month> \
        [--no-regen] [MATRICULE ...]
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.backtest.employee_matching import match_employees, resolve_company_id
from scripts.backtest.pdf_loader import load_reference_bulletins
from scripts.backtest.bulletins_source import resolve_bulletin_pdf
from scripts.backtest.backtest_company_payroll import _generate_payslip, compare_matches
from app.modules.payroll.backtest.thresholds import default_thresholds

TIER_S_KEYS = {"salaire_brut", "net_imposable", "montant_net_social",
               "net_a_payer", "pas_montant"}


def load_refs(company: str, year: int, month: int):
    """Charge les bulletins de référence en résolvant le bon PDF mensuel."""
    try:
        pdf = resolve_bulletin_pdf(company, year, month)
    except Exception:
        pdf = None
    return load_reference_bulletins(company, year, month, pdf_path=pdf)


def main():
    args = sys.argv[1:]
    if len(args) < 3:
        print(__doc__)
        return
    company, year, month = args[0], int(args[1]), int(args[2])
    rest = args[3:]
    regen = "--no-regen" not in rest
    wanted = set(a for a in rest if not a.startswith("--"))

    refs = load_refs(company, year, month)
    cid = resolve_company_id(company)
    matched = match_employees(cid, refs).matched
    if wanted:
        matched = [m for m in matched if m.matricule in wanted]

    if regen:
        for m in matched:
            try:
                _generate_payslip(m, year, month)
            except Exception as exc:
                print(f"[GEN ERR {m.matricule}] {exc}", flush=True)

    reports = compare_matches(matched, year, month, thresholds=default_thresholds(),
                              systemic_deltas={}, correction_attempts={})
    reports.sort(key=lambda r: r.tier_s_max_delta)

    n_conv = 0
    n_20 = 0
    for r in reports:
        d = r.tier_s_max_delta
        if d <= 0.05:
            n_conv += 1
        if d <= 20.0:
            n_20 += 1
        flag = "OK " if d <= 0.05 else ("~  " if d <= 20.0 else "   ")
        detail = []
        for ln in r.lines:
            if ln.tier == "S" and abs(ln.delta) > 0.05:
                detail.append(f"{ln.field_key}={ln.delta:+.2f}(ref {ln.reference_value} vs {ln.actual_value})")
        print(f"{flag}[{r.matricule:14s}] tierS={d:9.2f}  {r.employee_name}", flush=True)
        for dd in detail:
            print(f"        {dd}", flush=True)

    print(f"\n=== {company} {year}-{month:02d} : {n_conv}/{len(reports)} convergés (≤0,05€) "
          f"| {n_20}/{len(reports)} sous ±20€ ===", flush=True)


if __name__ == "__main__":
    main()
