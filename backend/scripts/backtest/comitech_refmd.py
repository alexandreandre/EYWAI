#!/usr/bin/env python3
"""Genere les bulletins de reference Comitech en Markdown pour un mois donne,
en pointant sur le PDF du dossier Bulletins/ (les autres mois que mai ne sont
pas dans Config/). Sortie: scratchpad/comitech_ref/<AAAA-MM>/<MAT>.md
"""
from __future__ import annotations
import argparse
from pathlib import Path

from scripts.backtest.pdf_loader import extract_pdf_text
from scripts.backtest.bulletins_source import resolve_bulletin_pdf
from app.modules.payroll.backtest.reference_parser import parse_cegid_text
from scripts.backtest.export_reference_md import (
    _bulletin_markdown, _split_raw_text_per_matricule, _slug, _fmt,
)

OUT_ROOT = Path("/private/tmp/claude-501/-Users-alex-Desktop-EYWAI-EYWAI/"
                "cfdb3f75-b90e-430f-922f-effaf4ea2dbd/scratchpad/comitech_ref")


def export(year: int, month: int) -> Path:
    pdf = resolve_bulletin_pdf("Comitech Composite", year, month)
    full_text = extract_pdf_text(pdf)
    references = parse_cegid_text(full_text)
    raw_blocks = _split_raw_text_per_matricule(full_text)
    out_dir = OUT_ROOT / f"{year}-{month:02d}"
    out_dir.mkdir(parents=True, exist_ok=True)
    idx = [f"# Comitech {month:02d}/{year} ({pdf.name})", "",
           "| Matricule | Brut | Net imp | MNS | Net avant imp | Net a payer |",
           "|---|---|---|---|---|---|"]
    for mat in sorted(references.keys()):
        ref = references[mat]
        md = _bulletin_markdown(mat, ref, raw_blocks.get(mat))
        (out_dir / f"{_slug(mat)}.md").write_text(md, encoding="utf-8")
        idx.append(f"| {mat} | {_fmt(ref.salaire_brut)} | {_fmt(ref.net_imposable)} | "
                   f"{_fmt(ref.montant_net_social)} | {_fmt(ref.net_avant_impot)} | "
                   f"{_fmt(ref.net_a_payer)} |")
    (out_dir / "README.md").write_text("\n".join(idx) + "\n", encoding="utf-8")
    print(f"{month:02d}/{year}: {len(references)} bulletins -> {out_dir}")
    return out_dir


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, default=2026)
    ap.add_argument("--months", type=int, nargs="+", default=[1, 2, 3, 4, 5, 6])
    a = ap.parse_args()
    for m in a.months:
        try:
            export(a.year, m)
        except Exception as e:
            print(f"{m:02d}: ERREUR {type(e).__name__}: {e}")
