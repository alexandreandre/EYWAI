#!/usr/bin/env python3
"""Extrait tous les elements variables d'un bulletin Colorplast pour un mois.

Parse le PDF reel (par bloc matricule) et affiche, par salarie : base rate,
jours CP, absences non payees (jour+heures), HS conjoncturelles 25/50, primes
(exceptionnelle, transport, note de frais, mutuelle famille), acompte, et les
cibles (brut, net imposable, MNS, net avant impot).

Usage:
    .venv/bin/python -m scripts.backtest.colorplast_extract --month 2
"""
from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path

from scripts.backtest.bulletins_source import resolve_bulletin_pdf


def extract(company: str, year: int, month: int) -> None:
    pdf = resolve_bulletin_pdf(company, year, month)
    txt = subprocess.run(["pdftotext", "-layout", str(pdf), "-"],
                         capture_output=True, text=True).stdout
    parts = re.split(r"Matricule\s*:\s*(\w+)", txt)
    seen = set()
    print(f"=== {company} {month:02d}/{year} : {pdf.name} ===")
    for i in range(1, len(parts), 2):
        mat = parts[i]
        if mat in seen:
            continue
        seen.add(mat)
        block = parts[i + 1]

        def f1(pat, grp=1):
            m = re.search(pat, block)
            return m.group(grp) if m else None

        base_rate = f1(r"SALAIRE DE BASE\s+151\.67\s+([\d.]+)")
        base_mnt = f1(r"SALAIRE DE BASE\s+151\.67\s+[\d.]+\s+([\d.]+)")
        cps = re.findall(r"Cong[ée]s pay[ée]s\s*:\s*(\d{6})", block)
        abs_np = re.findall(r"Abs\.?\s*Abs aut nonpay[ée]\s+(\d{6})\s+([\d.]+)\s+[\d.]+\s+([\d.]+)", block)
        hs25 = f1(r"Heures suppl[ée]mentaires 25\s+([\d.]+)")
        hs50 = f1(r"Heures suppl[ée]mentaires 50\s+([\d.]+)")
        prime_exc = f1(r"BPA Prime exceptionnelle\s+([\d.]+)")
        transport = f1(r"STRA Indemnit[ée] de transport\s+([\d.]+)")
        note_frais = f1(r"SNDF Rbst note de frais\s+([\d.]+)")
        note_frais2 = f1(r"Remboursement de notes? de frais\s+([\d.]+)")
        mut_fam = f1(r"SMU2 GAN MUTUELLE FAMILLE\s+(-?[\d.]+)")
        acompte = f1(r"Acompte\s+([\d.]+)\s+[\d.]+\s*$")
        acompte2 = f1(r"Acompte\s+([\d.]+)")
        report_nap = f1(r"Report NAP.*?(-?[\d.]+)")
        saisie = f1(r"Saisie\D+(-?[\d.]+)")
        prime_anc = f1(r"BANC Prime ancienn?et[ée]\s+[\d.]+\s+([\d.]+)")
        brut = f1(r"SALAIRE BRUT\s+([\d.]+)")
        net_imp = f1(r"NET IMPOSABLE\s+([\d.]+)")
        mns = f1(r"MONTANT NET SOCIAL\s+([\d.]+)")
        nav = f1(r"NET A PAYER AVANT IMPOT SUR LE REVENU\s+([\d.]+)")

        print(f"\n#### {mat}  base_rate={base_rate} base_mnt={base_mnt} prime_anc={prime_anc}")
        print(f"   cp={cps} abs_np={abs_np}")
        print(f"   hs25={hs25} hs50={hs50} prime_exc={prime_exc} transport={transport}")
        print(f"   note_frais(SNDF)={note_frais} note_frais(Remb)={note_frais2} mut_fam={mut_fam}")
        print(f"   report_nap={report_nap} saisie={saisie} acompte={acompte or acompte2}")
        print(f"   TARGETS brut={brut} net_imp={net_imp} mns={mns} net_avant_impot={nav}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--company", default="Colorplast")
    ap.add_argument("--year", type=int, default=2026)
    ap.add_argument("--month", type=int, required=True)
    args = ap.parse_args()
    extract(args.company, args.year, args.month)


if __name__ == "__main__":
    main()
