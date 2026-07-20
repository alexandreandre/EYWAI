#!/usr/bin/env python3
"""Exporte les bulletins de référence Cegid (PDF) en Markdown, un fichier par salarié.

Réutilise le parseur existant (`pdf_loader.load_reference_bulletins`) pour les
figures clés (fiables, déjà validées contre la DSN) et joint le texte brut extrait
du PDF (`pdftotext -layout`) pour l'inspection ligne par ligne quand les rubriques
détaillées ont un souci de colonne (déjà rencontré sur des bulletins Cegid multi-
colonnes).

Usage:
    python -m scripts.backtest.export_reference_md --company Colorplast --year 2026 --month 5
    python -m scripts.backtest.export_reference_md --all --year 2026 --month 5
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.backtest.pdf_loader import (
    extract_pdf_text,
    find_reference_pdf,
    resolve_company_folder,
)
from scripts.backtest.bulletins_source import resolve_bulletin_pdf
from app.modules.payroll.backtest.reference_parser import parse_cegid_text

ALL_COMPANIES = [
    "Cartol",
    "Colorplast",
    "Comitech Composite",
    "Lewis",
    "MBC",
    "Maji",
    "Zone",
]


def _slug(matricule: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "_", matricule).strip("_") or "SALARIE"


def _fmt(value) -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:,.2f} €".replace(",", " ")
    return str(value)


def _split_raw_text_per_matricule(full_text: str) -> dict[str, str]:
    """Découpe le texte brut pdftotext en blocs par salarié (repère 'Matricule :')."""
    blocks: dict[str, list[str]] = {}
    current: str | None = None
    for line in full_text.splitlines():
        m = re.search(r"Matricule\s*:\s*(\S+)", line)
        if m:
            current = m.group(1).upper()
            blocks.setdefault(current, [])
        if current:
            blocks[current].append(line)
    return {k: "\n".join(v) for k, v in blocks.items()}


def _fmt_pct(value) -> str:
    if value is None:
        return "—"
    return f"{value:.2f} %"


def _fmt_int(value) -> str:
    if value is None:
        return "—"
    return str(int(value))


def _bulletin_markdown(matricule: str, ref, raw_block: str | None) -> str:
    nom_complet = (ref.nom_complet or "").splitlines()[0].strip() if ref.nom_complet else ""
    lines = [
        f"# Bulletin réel — {matricule}",
        "",
        f"**Nom complet** : {nom_complet or '—'}  ",
        f"**Date de paiement** : {ref.date_paiement or '—'}  ",
        f"**Coefficient** : {_fmt_int(ref.coefficient)}",
        "",
        "## Figures clés (fiables — comparer en premier)",
        "",
        "| Champ | Valeur |",
        "|---|---|",
        f"| Salaire brut | {_fmt(ref.salaire_brut)} |",
        f"| Net imposable | {_fmt(ref.net_imposable)} |",
        f"| Montant net social (MNS) | {_fmt(ref.montant_net_social)} |",
        f"| Net avant impôt | {_fmt(ref.net_avant_impot)} |",
        f"| Taux PAS | {_fmt_pct(ref.pas_taux)} |",
        f"| Montant PAS | {_fmt(ref.pas_montant)} |",
        f"| **Net à payer** | **{_fmt(ref.net_a_payer)}** |",
        f"| Coût total employeur | {_fmt(ref.cout_total_employeur)} |",
        f"| Solde CP (N) | {_fmt(ref.cp_solde_n)} |",
        "",
    ]

    if ref.rubriques:
        lines += [
            "## Rubriques détaillées (parsées automatiquement — vérifier contre le texte brut ci-dessous en cas de doute, colonnes parfois mal alignées sur les PDF Cegid multi-colonnes)",
            "",
            "| Libellé | Base | Taux salarial | Montant salarial | Montant patronal |",
            "|---|---|---|---|---|",
        ]
        for r in ref.rubriques:
            lines.append(
                f"| {r.libelle} | {_fmt(r.base)} | {_fmt(r.taux_salarial)} | "
                f"{_fmt(r.montant_salarial)} | {_fmt(r.montant_patronal)} |"
            )
        lines.append("")

    if raw_block:
        lines += [
            "## Texte brut (extraction `pdftotext -layout`, pour vérification manuelle)",
            "",
            "```",
            raw_block.strip(),
            "```",
            "",
        ]

    return "\n".join(lines)


def export_company(company_name: str, year: int, month: int) -> Path:
    # resolve_bulletin_pdf trouve le PDF du BON mois (find_reference_pdf retombait
    # sur le PDF de mai pour tous les mois de Cartol → MD/extract faux → reconcile
    # revertait tout). Repli sur find_reference_pdf si le résolveur mensuel échoue.
    pdf_path = resolve_bulletin_pdf(company_name, year, month) or find_reference_pdf(
        company_name, year, month
    )
    full_text = extract_pdf_text(pdf_path)
    references = parse_cegid_text(full_text)
    raw_blocks = _split_raw_text_per_matricule(full_text)

    company_dir = resolve_company_folder(company_name)
    cp_dirs = list(company_dir.glob("Compteur CP*"))
    out_dir = (cp_dirs[0] if cp_dirs else company_dir) / f"bulletins_md_{year}-{month:02d}"
    out_dir.mkdir(parents=True, exist_ok=True)

    index_lines = [f"# Bulletins réels — {company_name} — {month:02d}/{year}", ""]
    index_lines.append("| Matricule | Salaire brut | Net imposable | MNS | Net à payer |")
    index_lines.append("|---|---|---|---|---|")

    for matricule in sorted(references.keys()):
        ref = references[matricule]
        raw_block = raw_blocks.get(matricule)
        md = _bulletin_markdown(matricule, ref, raw_block)
        out_path = out_dir / f"{_slug(matricule)}.md"
        out_path.write_text(md, encoding="utf-8")
        index_lines.append(
            f"| [{matricule}](./{out_path.name}) | {_fmt(ref.salaire_brut)} | "
            f"{_fmt(ref.net_imposable)} | {_fmt(ref.montant_net_social)} | "
            f"{_fmt(ref.net_a_payer)} |"
        )

    (out_dir / "README.md").write_text("\n".join(index_lines) + "\n", encoding="utf-8")
    print(f"{company_name}: {len(references)} bulletin(s) exporté(s) -> {out_dir}")
    return out_dir


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--company", help="Nom de l'entreprise (Config/<Entreprise>)")
    parser.add_argument("--all", action="store_true", help="Exporter toutes les entreprises connues")
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--month", type=int, required=True)
    args = parser.parse_args()

    if not args.company and not args.all:
        parser.error("Préciser --company <Nom> ou --all")

    companies = ALL_COMPANIES if args.all else [args.company]
    for company in companies:
        try:
            export_company(company, args.year, args.month)
        except Exception as exc:
            print(f"{company}: ERREUR — {exc}")


if __name__ == "__main__":
    main()
