#!/usr/bin/env python3
"""Recalcule company_dsn_payroll_totals depuis batches committed (sans ré-import)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.modules.dsn_import.application.payroll_totals_recompute import (  # noqa: E402
    recompute_committed_batches,
)


def _default_search_dirs(extra: list[str]) -> list[Path]:
    dirs = [REPO_ROOT, REPO_ROOT / "data" / "dsn", BACKEND_ROOT / "data" / "dsn"]
    for raw in extra:
        path = Path(raw).expanduser()
        dirs.append(path)
        if path.is_dir() and path.name.upper() != "DSN":
            dirs.extend(p for p in path.rglob("DSN") if p.is_dir())
    return dirs


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Recalcule les totaux paie DSN (parser corrigé, sans ré-import)."
    )
    parser.add_argument(
        "--dsn-dir",
        action="append",
        default=[],
        help="Répertoire additionnel où chercher les fichiers DSN (répétable).",
    )
    parser.add_argument(
        "--stored-only",
        action="store_true",
        help="Ne pas re-parser les fichiers DSN, normaliser uniquement les items stockés.",
    )
    parser.add_argument("--limit", type=int, default=500, help="Nombre max de batches.")
    args = parser.parse_args()

    search_dirs = _default_search_dirs(args.dsn_dir)
    report = recompute_committed_batches(
        search_dirs=search_dirs,
        limit=args.limit,
        prefer_dsn_file=not args.stored_only,
    )

    print(
        f"Terminé — {report['batches_processed']} batch(es), "
        f"{report['periods_upserted']} période(s) upsertées "
        f"({report['from_dsn_file']} via fichier DSN, "
        f"{report['from_stored_items']} via items stockés)."
    )
    for detail in report["details"][:20]:
        print(
            f"  batch {detail['batch_id'][:8]}… "
            f"{detail.get('period_min')} source={detail['source']} counts={detail['counts']}"
        )
    if len(report["details"]) > 20:
        print(f"  … et {len(report['details']) - 20} autre(s) batch(es)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
