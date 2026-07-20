"""Mesure baseline Cartol: génère tous les matchés d'un mois, dump deltas par champ.

Usage: .venv/bin/python -m scripts.backtest.cartol_measure --month 5 [--emp NOM ...]
Sort: JSON scratchpad/cartol_measure_<MM>.json + table triée par écart croissant.
"""
from __future__ import annotations
import argparse, json, sys, traceback
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.backtest.bulletins_source import resolve_bulletin_pdf
from scripts.backtest.employee_matching import match_employees, resolve_company_id
from scripts.backtest.pdf_loader import load_reference_bulletins
from scripts.backtest.backtest_company_payroll import _generate_payslip, compare_matches
from app.modules.payroll.backtest.thresholds import default_thresholds

COMPANY = "Cartol"
KEY = ["salaire_brut", "net_imposable", "montant_net_social", "net_a_payer",
       "prime_anciennete", "participation", "acompte_participation", "prevoyance_gan", "mutuelle_gan"]
SC = Path("/private/tmp/claude-501/-Users-alex-Desktop-EYWAI-EYWAI/"
          "cfdb3f75-b90e-430f-922f-effaf4ea2dbd/scratchpad")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--month", type=int, required=True)
    ap.add_argument("--year", type=int, default=2026)
    ap.add_argument("--emp", nargs="*", default=None)
    a = ap.parse_args()
    pdf = resolve_bulletin_pdf(COMPANY, a.year, a.month)
    refs = load_reference_bulletins(COMPANY, a.year, a.month, pdf_path=pdf)
    cid = resolve_company_id(COMPANY)
    matched = match_employees(cid, refs).matched
    if a.emp:
        want = set(a.emp); matched = [m for m in matched if m.matricule in want]
    out = {}
    for m in matched:
        try:
            _generate_payslip(m, a.year, a.month)
            rep = list(compare_matches([m], a.year, a.month, thresholds=default_thresholds(),
                                       systemic_deltas={}, correction_attempts={}))[0]
            d = {ln.field_key: {"ref": ln.reference_value, "eywai": ln.actual_value,
                                "delta": ln.delta} for ln in rep.lines if ln.field_key in KEY}
            out[m.matricule] = {"tierS": round(rep.tier_s_max_delta, 2), "fields": d}
        except Exception as e:
            out[m.matricule] = {"tierS": 99999, "error": f"{type(e).__name__}: {e}"}
            traceback.print_exc()
    (SC / f"cartol_measure_{a.month:02d}.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    conv = sum(1 for v in out.values() if v["tierS"] <= 0.05)
    print(f"\n=== Cartol {a.month:02d}/{a.year}: {conv}/{len(out)} convergés (<=0.05) ===")
    for mat, v in sorted(out.items(), key=lambda x: x[1]["tierS"]):
        f = v.get("fields", {})
        def dl(k):
            return f.get(k, {}).get("delta")
        parts = []
        for k, lbl in [("salaire_brut", "brut"), ("net_imposable", "nimp"),
                       ("montant_net_social", "mns"), ("net_a_payer", "nap")]:
            dv = dl(k)
            if dv is not None and abs(dv) > 0.05:
                parts.append(f"{lbl}{dv:+.0f}")
        print(f"  {mat:14s} tierS={v['tierS']:>9.2f}  {' '.join(parts)}"
              + (f"  ERR:{v['error']}" if 'error' in v else ""))


if __name__ == "__main__":
    main()
