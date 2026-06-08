#!/usr/bin/env python3
"""Orchestrateur versement mobilité — scrape VMRR puis écrit payroll_config."""

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

_SCRAPING = Path(__file__).resolve().parent.parent
if str(_SCRAPING) not in sys.path:
    sys.path.insert(0, str(_SCRAPING))

from core.base_orchestrator import is_dry_run  # noqa: E402
from core.env import load_env  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] - %(message)s")


def main() -> None:
    parser = argparse.ArgumentParser(description="Orchestrateur VM")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Scrape sans écrire en base",
    )
    args = parser.parse_args()
    if args.dry_run:
        import os

        os.environ["EYWAI_SCRAPING_DRY_RUN"] = "1"

    load_env()
    dry = is_dry_run()
    from VM import scrape_vmrr_from_urssaf, upsert_payroll_config  # noqa: WPS433

    data, links = scrape_vmrr_from_urssaf()
    success = bool(data)

    if success and not dry:
        try:
            upsert_payroll_config("taux_vmrr", data, source_links=links)
        except Exception as exc:
            logging.error("Erreur Supabase taux_vmrr: %s", exc)
            success = False
    elif dry:
        logging.info("Dry-run VM — pas d'écriture Supabase")

    out = {
        "scraper": "VM",
        "success": success,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "config_key": "taux_vmrr",
        "data": {"rows": len(data or [])},
        "sources_used": links or ["VM.py"],
    }
    print(json.dumps(out, ensure_ascii=False))
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
