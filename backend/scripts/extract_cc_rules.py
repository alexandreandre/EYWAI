#!/usr/bin/env python3
"""Extraction batch des règles CC paie via IA (OpenRouter Gemini 2.5 Flash)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Ajouter backend/ au path pour imports app.*
_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Extrait les règles paie depuis les textes CC du catalogue."
    )
    parser.add_argument("--idcc", action="append", help="IDCC à traiter (répétable)")
    parser.add_argument(
        "--priority-only",
        action="store_true",
        help="Traiter le lot prioritaire (1486, 1090, 1516, 2098, 0044)",
    )
    parser.add_argument(
        "--all",
        dest="all_catalog",
        action="store_true",
        help="Traiter tout le catalogue actif avec PDF",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simuler sans appel IA",
    )
    args = parser.parse_args()

    from app.modules.collective_agreements.rules.service import get_cc_rules_service

    service = get_cc_rules_service()
    outcomes = service.extract_batch(
        idcc_list=args.idcc,
        all_catalog=args.all_catalog,
        priority_only=args.priority_only or (
            not args.idcc and not args.all_catalog
        ),
        dry_run=args.dry_run,
    )

    summary = {
        "total": len(outcomes),
        "succeeded": sum(1 for o in outcomes if o.success),
        "failed": sum(1 for o in outcomes if not o.success),
        "results": [
            {
                "success": o.success,
                "idcc": o.idcc,
                "agreement_id": o.agreement_id,
                "error": o.error,
                "tokens_used": o.tokens_used,
                "confidence": o.confidence,
            }
            for o in outcomes
        ],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
