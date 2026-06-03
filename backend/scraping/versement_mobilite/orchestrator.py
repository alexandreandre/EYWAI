#!/usr/bin/env python3
"""Orchestrateur versement mobilité — exécute VM.py avec dry-run."""

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
    from VM import scrape_vmrr_from_urssaf  # noqa: WPS433

    if dry:
        logging.info("Dry-run VM — pas d'écriture Supabase")
        data, _links = scrape_vmrr_from_urssaf()
        out = {
            "scraper": "VM",
            "success": bool(data),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "config_key": "taux_vmrr",
            "data": {"rows": len(data or [])},
            "sources_used": ["VM.py"],
        }
        print(json.dumps(out, ensure_ascii=False))
        sys.exit(0 if out["success"] else 1)

    import VM as vm_mod  # noqa: WPS433

    vm_mod.main()
    out = {
        "scraper": "VM",
        "success": True,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "config_key": "taux_vmrr",
        "data": {},
        "sources_used": ["VM.py"],
    }
    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
