#!/usr/bin/env python3
"""Extrait toutes les figures cles + rubriques parsees des bulletins Comitech
pour tous les mois, dans un JSON structure (source de donnees du setup)."""
from __future__ import annotations
import json
import re
from pathlib import Path
from scripts.backtest.pdf_loader import extract_pdf_text
from scripts.backtest.bulletins_source import resolve_bulletin_pdf
from app.modules.payroll.backtest.reference_parser import parse_cegid_text

# Acompte sur participation (net-only, non capté par le parser Cegid partagé) :
# « SINT Acompte sur participation 2025  -500.00 ».
_ACOMPTE_PART_RE = re.compile(
    r"Acompte sur participation\s*(?:\d{4})?\s+(-?[\d]+\.\d{2})", re.IGNORECASE
)

OUT = Path("/private/tmp/claude-501/-Users-alex-Desktop-EYWAI-EYWAI/"
           "cfdb3f75-b90e-430f-922f-effaf4ea2dbd/scratchpad/comitech_extract.json")


def main():
    result = {}
    for month in (1, 2, 3, 4, 5, 6):
        try:
            pdf = resolve_bulletin_pdf("Comitech Composite", 2026, month)
            refs = parse_cegid_text(extract_pdf_text(pdf))
        except Exception as e:
            print(f"{month}: ERR {e}")
            continue
        mdata = {}
        for mat, r in refs.items():
            rubriques = []
            for rb in (r.rubriques or []):
                rubriques.append({
                    "lib": rb.libelle, "base": rb.base,
                    "ts": rb.taux_salarial, "ms": rb.montant_salarial,
                    "mp": rb.montant_patronal,
                })
            _acp = _ACOMPTE_PART_RE.search(r.raw_text or "")
            mdata[mat] = {
                "brut": r.salaire_brut, "net_imp": r.net_imposable,
                "mns": r.montant_net_social, "net_av": r.net_avant_impot,
                "nap": r.net_a_payer, "pas_taux": r.pas_taux, "pas_mt": r.pas_montant,
                "coeff": r.coefficient, "cp_solde_n": r.cp_solde_n,
                "rub": rubriques,
                "acompte_part": abs(float(_acp.group(1))) if _acp else None,
            }
        result[str(month)] = mdata
        print(f"{month}: {len(mdata)} bulletins")
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=1))
    print("->", OUT)


if __name__ == "__main__":
    main()
