"""Diagnostic complet par salarié pour le backtest MBC mai 2026.

Pour chaque salarié non convergé, détecte :
- écart Entré(e) le / Ancienneté (reprise d'ancienneté à appliquer)
- mentions arrêt maladie / rechute / maintien de salaire
- lignes taggées (BAA/BPAN/BSIC/SPAN/SND/SAVx/SCAN/SINT/EMUx/EPRx) non
  reconnues par les regex de mbc_batch_fix.py (pour repérer les codes non
  encore catalogués)
- tier-S actuel

Usage (depuis backend/) :
    .venv/bin/python -m scripts.backtest.mbc_full_diagnosis
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.core.database import supabase
from scripts.backtest.employee_matching import match_employees, resolve_company_id
from scripts.backtest.pdf_loader import load_reference_bulletins
from scripts.backtest.backtest_company_payroll import compare_matches
from app.modules.payroll.backtest.thresholds import default_thresholds
from scripts.backtest.mbc_batch_fix import (
    _PREVOYANCE_RE,
    _MUTUELLE_RE,
    _PARTICIPATION_RE,
    _ACOMPTE_RE,
    _PRET_RE,
    _CANTINE_RE,
    _TAGGED_PRIME_RE,
)

COMPANY = "Mont Blanc Composite"
YEAR, MONTH = 2026, 5

_ENTREE_RE = re.compile(r"Entr[ée]\(e\)\s*le\s*:\s*(\d{2}/\d{2}/\d{4})")
_ANCIENNETE_RE = re.compile(r"Anciennet[ée]\s*:\s*(\d{2}/\d{2}/\d{4})")
_MALADIE_RE = re.compile(
    r"(Absence maladie|Prol\.rechute|Maintien de salaire|arret|arrêt)", re.IGNORECASE
)
_ALL_TAGGED_RE = re.compile(
    r"^\s*([A-Z]{3,5})\s+([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ'.() ]{2,40}?)\s+"
    r"(-?[\d.]+\.\d{2,4})(?=\s{2,}|\s*$)",
    re.MULTILINE,
)
_KNOWN_CODES = {"EMU1", "EMU2", "EMU3", "EMU4", "EMU5", "EMU6", "EPR1", "EPR2", "EPR3",
                 "BAA", "BPAN", "BSIC", "SPAN", "SND6", "SNDF", "SAVV", "SAVU", "SAVP",
                 "SAWZ", "SAWY", "SBUS", "SCAN", "SINT", "BANC", "BQCP", "EWA2", "EWZC"}


def main():
    refs = load_reference_bulletins(COMPANY, YEAR, MONTH)
    cid = resolve_company_id(COMPANY)
    matches = match_employees(cid, refs).matched
    results = list(
        compare_matches(
            matches, YEAR, MONTH, thresholds=default_thresholds(),
            systemic_deltas={}, correction_attempts={},
        )
    )
    tier_s_by_matricule = {r.matricule: r.tier_s_max_delta for r in results}
    matches_by_matricule = {m.matricule: m for m in matches}

    ordered = sorted(tier_s_by_matricule.items(), key=lambda kv: kv[1])

    for matricule, tier_s in ordered:
        if tier_s <= 0.05:
            continue
        m = matches_by_matricule[matricule]
        text = m.reference.raw_text or ""
        flags = []

        entree_m = _ENTREE_RE.search(text)
        ancien_m = _ANCIENNETE_RE.search(text)
        if entree_m and ancien_m and entree_m.group(1) != ancien_m.group(1):
            flags.append(f"ANCIENNETE_MISMATCH entree={entree_m.group(1)} ancien={ancien_m.group(1)}")

        if _MALADIE_RE.search(text):
            flags.append("ARRET_MALADIE_MENTION")

        unknown_codes = set()
        for code, label, amount in _ALL_TAGGED_RE.findall(text):
            if code not in _KNOWN_CODES:
                unknown_codes.add(f"{code}({label.strip()[:25]}={amount})")
        if unknown_codes:
            flags.append("UNKNOWN_TAGS: " + "; ".join(sorted(unknown_codes)[:6]))

        emp = (
            supabase.table("employees")
            .select("specificites_paie")
            .eq("id", m.employee_id)
            .single()
            .execute()
            .data
        )
        sp = (emp or {}).get("specificites_paie") or {}
        prevoyance = sp.get("prevoyance", {})
        if _PREVOYANCE_RE.search(text) and prevoyance.get("adhesion"):
            lignes = prevoyance.get("lignes_specifiques") or []
            if not lignes or lignes[0].get("patronal") != 0.005 or lignes[0].get("salarial") != 0.005:
                flags.append("PREVOYANCE_RATE_WRONG")
        if _PREVOYANCE_RE.search(text) and not prevoyance.get("adhesion"):
            flags.append("PREVOYANCE_ADHESION_MISSING")

        print(f"{matricule:15s} tier-S={tier_s:8.2f}  " + (" | ".join(flags) if flags else "(rien détecté automatiquement)"))


if __name__ == "__main__":
    main()
