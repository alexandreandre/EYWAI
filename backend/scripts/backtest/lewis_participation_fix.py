"""Lewis mai 2026 - ajoute la ligne Participation 2025 manquante en
monthly_inputs pour chaque salarie dont le bulletin reel en porte une mais
dont aucune saisie participation n'existe en base (gap DATA pur, confirme
via MAIRESSE/MASLOWSKI/DURAND : _is_participation_numeraire_input deja
cable cote moteur forfait ET heures, seule la donnee manquait).

Revert-safe, UN SALARIE A LA FOIS (chaque ajout individuellement teste/garde
ou reverte), deepcopy des snapshots.

Usage : .venv/bin/python -m scripts.backtest.lewis_participation_fix [MATRICULE ...]
        (sans arg = tous les matches)
"""
from __future__ import annotations
import copy, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.core.database import get_supabase_admin_client
from scripts.backtest.employee_matching import match_employees, resolve_company_id
from scripts.backtest.pdf_loader import load_reference_bulletins
from scripts.backtest.backtest_company_payroll import _generate_payslip, compare_matches
from app.modules.payroll.backtest.thresholds import default_thresholds

COMPANY = "Lewis"
YEAR, MONTH = 2026, 5

_PARTICIPATION_RE = re.compile(
    r"^\s*Participation(?:\s*2025)?\s+([\d]+\.\d{2})\s+([\d]+\.\d{2})(?=\s{2,}|\s*$)",
    re.MULTILINE,
)


def tier_s(m):
    _generate_payslip(m, YEAR, MONTH)
    for r in compare_matches([m], YEAR, MONTH, thresholds=default_thresholds(),
                              systemic_deltas={}, correction_attempts={}):
        return r.tier_s_max_delta
    return float("inf")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    admin = get_supabase_admin_client()
    refs = load_reference_bulletins(COMPANY, YEAR, MONTH)
    cid = resolve_company_id(COMPANY)
    matched = match_employees(cid, refs).matched
    if args:
        matched = [m for m in matched if m.matricule in set(args)]

    for m in matched:
        ref_text = getattr(m.reference, "raw_text", None) or ""
        mo = _PARTICIPATION_RE.search(ref_text)
        if not mo:
            continue
        try:
            amount = float(mo.group(2))
        except ValueError:
            print(f"[{m.matricule}] montant participation illisible: {mo.group(2)!r}")
            continue
        if amount <= 0:
            continue

        existing = (
            admin.table("monthly_inputs").select("*")
            .match({"employee_id": m.employee_id, "year": YEAR, "month": MONTH})
            .execute().data
        ) or []
        already = any("participation" in (r.get("name") or "").lower() for r in existing)
        if already:
            print(f"[{m.matricule}] participation deja presente en base, skip")
            continue

        before = tier_s(m)
        snap = copy.deepcopy(existing)

        admin.table("monthly_inputs").insert({
            "employee_id": m.employee_id,
            "company_id": cid,
            "year": YEAR,
            "month": MONTH,
            "name": "Participation 2025",
            "amount": amount,
            "is_socially_taxed": False,
            "is_taxable": True,
        }).execute()

        after = tier_s(m)
        keep = after < before - 0.01
        if keep:
            print(f"[{m.matricule}] participation {amount} EUR ajoutee : {before:.2f} -> {after:.2f}  GARDE")
        else:
            admin.table("monthly_inputs").delete().match(
                {"employee_id": m.employee_id, "year": YEAR, "month": MONTH, "name": "Participation 2025"}
            ).execute()
            _generate_payslip(m, YEAR, MONTH)
            print(f"[{m.matricule}] participation {amount} EUR essayee : {before:.2f} -> {after:.2f}  REVERT")


if __name__ == "__main__":
    main()
