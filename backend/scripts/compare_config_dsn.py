#!/usr/bin/env python3
"""Compare une DSN EYWAI générée à une DSN Cegid de référence (lecture seule).

Exemples :
  python -m scripts.compare_config_dsn \\
    --reference Config/Colorplast/DSN/000005_0126_000001\\ \\(1\\).dsn \\
    --actual /tmp/dsn_mensuelle_2026_01.dsn

  python -m scripts.compare_config_dsn \\
    --company Colorplast --period 2026-01 \\
    --actual /tmp/dsn_mensuelle_2026_01.dsn

Aucun écriture en base : sorties JSON/Markdown locales uniquement.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.modules.dsn_compare.application.comparator import compare_dsn_bytes  # noqa: E402
from app.modules.dsn_compare.application.report_writer import (  # noqa: E402
    report_to_markdown,
    write_reports,
)

CONFIG_ROOT = REPO_ROOT / "Config"

COMPANY_ALIASES = {
    "colorplast": "Colorplast",
    "cartol": "Cartol",
    "comitech": "Comitech Composite",
    "comitech composite": "Comitech Composite",
    "lewis": "Lewis",
    "mbc": "MBC",
    "maji": "Maji",
}


def _resolve_reference(company: str | None, period: str | None, reference: str | None) -> Path:
    if reference:
        path = Path(reference)
        if not path.is_absolute():
            path = REPO_ROOT / path
        if not path.exists():
            raise FileNotFoundError(f"Fichier référence introuvable : {path}")
        return path
    if not company or not period:
        raise ValueError("Indiquer --reference ou (--company et --period)")
    folder = COMPANY_ALIASES.get(company.strip().lower(), company)
    year, month = period.split("-")
    dsn_dir = CONFIG_ROOT / folder / "DSN"
    if not dsn_dir.exists():
        raise FileNotFoundError(f"Dossier DSN introuvable : {dsn_dir}")
    # Convention Cegid : *_MMYY_*  ex. 000005_0126_000001 (1).dsn
    yy = year[2:]
    needle = f"_{int(month):02d}{yy}_"
    candidates = sorted(dsn_dir.glob("*.dsn"))
    matches = [p for p in candidates if needle in p.name]
    if not matches:
        raise FileNotFoundError(
            f"Aucune DSN pour {folder} {period} dans {dsn_dir} (motif {needle})"
        )
    return matches[-1]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Comparaison DSN EYWAI vs Cegid (read-only)")
    parser.add_argument("--reference", help="Chemin fichier DSN Cegid de référence")
    parser.add_argument("--actual", required=True, help="Chemin fichier DSN EYWAI générée")
    parser.add_argument("--company", help="Nom société (dossier Config)")
    parser.add_argument("--period", help="Période YYYY-MM")
    parser.add_argument("--json-out", help="Chemin rapport JSON")
    parser.add_argument("--md-out", help="Chemin rapport Markdown")
    parser.add_argument(
        "--print-md",
        action="store_true",
        help="Affiche le Markdown sur stdout",
    )
    args = parser.parse_args(argv)

    ref_path = _resolve_reference(args.company, args.period, args.reference)
    act_path = Path(args.actual)
    if not act_path.is_absolute():
        cwd_candidate = Path.cwd() / act_path
        repo_candidate = REPO_ROOT / act_path
        if cwd_candidate.exists():
            act_path = cwd_candidate.resolve()
        elif repo_candidate.exists():
            act_path = repo_candidate.resolve()
        else:
            act_path = repo_candidate
    if not act_path.exists():
        raise FileNotFoundError(f"Fichier actuel introuvable : {act_path}")

    report = compare_dsn_bytes(
        ref_path.read_bytes(),
        act_path.read_bytes(),
        reference_name=str(ref_path),
        actual_name=str(act_path),
    )
    report.meta.update(
        {
            "company": args.company,
            "period": args.period,
        }
    )

    written = write_reports(report, json_path=args.json_out, md_path=args.md_out)
    if args.print_md or not written:
        print(report_to_markdown(report))
    for kind, path in written.items():
        print(f"Rapport {kind} écrit : {path}", file=sys.stderr)

    # Code retour : 0 si pas d'ANOMALIE bloquante, 1 sinon
    has_anomaly = any(
        any(e.overall_verdict == "ANOMALIE" for e in est.employees)
        or any(ln.verdict == "ANOMALIE" for ln in est.summary_lines)
        for est in report.establishments
    )
    return 1 if has_anomaly else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001 — CLI
        print(f"Erreur : {exc}", file=sys.stderr)
        raise SystemExit(2)
