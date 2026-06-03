#!/usr/bin/env python3
"""Point d'entrée CLI : python -m agent.orchestrator [--from-queue] [--validate-sources]"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

_SCRAPING = Path(__file__).resolve().parent.parent
if str(_SCRAPING) not in sys.path:
    sys.path.insert(0, str(_SCRAPING))

from agent.orchestrator import run_repair_queue
from agent.source_validator import validate_all_official_sources
from core.env import ensure_scraping_path, load_env


def main() -> int:
    parser = argparse.ArgumentParser(description="Agent autonome réparation scraping")
    parser.add_argument(
        "--from-queue",
        action="store_true",
        help="Traite les jobs queued dans scraping_repair_jobs",
    )
    parser.add_argument(
        "--validate-sources",
        action="store_true",
        help="Validation mensuelle des URLs officielles (scraping_sources)",
    )
    parser.add_argument(
        "--max-jobs",
        type=int,
        default=5,
        help="Nombre max de jobs à traiter",
    )
    parser.add_argument(
        "--skip-git",
        action="store_true",
        help="Ne pas commit/push/PR (tests locaux)",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    ensure_scraping_path()
    load_env()

    if args.validate_sources:
        result = validate_all_official_sources()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get("failed", 0) == 0 else 1

    if args.from_queue:
        results = run_repair_queue(max_jobs=args.max_jobs, skip_git=args.skip_git)
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return 0 if all(r.get("success") for r in results) or not results else 1

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
