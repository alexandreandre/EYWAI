"""Dump des rubriques EYWAI d'un salarié MBC mai 2026 (depuis payslips.payslip_data).

Usage (depuis backend/):
    .venv/bin/python -m scripts.backtest.mbc_dump MATRICULE [MATRICULE ...]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.backtest.employee_matching import match_employees, resolve_company_id
from scripts.backtest.pdf_loader import load_reference_bulletins
from scripts.backtest.backtest_company_payroll import _load_payslip_data

COMPANY = "Mont Blanc Composite"
YEAR, MONTH = 2026, 5


def _walk(obj, prefix=""):
    """Aplati récursivement pour repérer les rubriques/montants."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from _walk(v, f"{prefix}.{k}" if prefix else str(k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _walk(v, f"{prefix}[{i}]")
    else:
        yield prefix, obj


def main():
    wanted = set(a for a in sys.argv[1:] if not a.startswith("--"))
    full = "--full" in sys.argv
    refs = load_reference_bulletins(COMPANY, YEAR, MONTH)
    cid = resolve_company_id(COMPANY)
    matched = match_employees(cid, refs).matched
    matched = [m for m in matched if m.matricule in wanted]
    for m in matched:
        data = _load_payslip_data(m.employee_id, YEAR, MONTH) or {}
        print(f"\n===== {m.matricule} ({m.first_name} {m.last_name}) =====")
        if full:
            print(json.dumps(data, indent=2, ensure_ascii=False, default=str))
            continue
        # Top-level scalar keys
        print("-- top-level --")
        for k in sorted(data):
            v = data[k]
            if not isinstance(v, (dict, list)):
                print(f"  {k} = {v}")
        # Rubriques
        for key in ("lignes", "rubriques", "lines", "bulletin_lines", "details"):
            if key in data and isinstance(data[key], list):
                print(f"-- {key} ({len(data[key])}) --")
                for ln in data[key]:
                    if isinstance(ln, dict):
                        lib = ln.get("libelle") or ln.get("label") or ln.get("name") or "?"
                        base = ln.get("base")
                        ms = ln.get("montant_salarial") or ln.get("montant") or ln.get("amount")
                        mp = ln.get("montant_patronal")
                        print(f"    {str(lib)[:45]:45s} base={base} sal={ms} pat={mp}")
    if not matched:
        print("Aucun matricule trouvé", wanted)


if __name__ == "__main__":
    main()
