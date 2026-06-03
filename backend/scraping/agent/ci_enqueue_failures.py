#!/usr/bin/env python3
"""Enqueue des jobs repair après échec dry-run CI."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

_SCRAPING = Path(__file__).resolve().parent.parent
if str(_SCRAPING) not in sys.path:
    sys.path.insert(0, str(_SCRAPING))

from agent.jobs import enqueue_repair_job
from agent.source_registry import fetch_official_source
from agent.triggers import context_for_orchestrator_failure
from core.env import BACKEND_ROOT, ensure_scraping_path, load_env
from core.supabase_io import init_supabase_client
from scraper_manifest import get_manifest


def _failed_scrapers_from_output(output: str) -> list[str]:
    failed: list[str] = []
    for line in output.splitlines():
        line = line.strip()
        if "FAIL" in line.upper() or "ÉCHEC" in line.upper() or "ECHEC" in line.upper():
            for entry in get_manifest():
                if entry.name in line:
                    failed.append(entry.name)
    return list(dict.fromkeys(failed))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tier", default=None, help="Filtrer par tier (critical, etc.)")
    args = parser.parse_args()

    ensure_scraping_path()
    load_env()
    supabase = init_supabase_client()

    cmd = [sys.executable, "scraping/test_scrapers.py", "--live", "--no-ai"]
    if args.tier:
        cmd.extend(["--tier", args.tier])

    proc = subprocess.run(
        cmd,
        cwd=str(BACKEND_ROOT),
        capture_output=True,
        text=True,
        timeout=900,
    )
    output = (proc.stdout or "") + (proc.stderr or "")

    failed = _failed_scrapers_from_output(output)
    if not failed:
        print("Aucun scraper identifié en échec — pas d'enqueue.")
        return proc.returncode

    for scraper_name in failed:
        official = fetch_official_source(supabase, scraper_name)
        enqueue_repair_job(
            supabase,
            scraper_name=scraper_name,
            trigger="ci_dry_run_failure",
            source_id=official.source_id if official else None,
            error_message=f"CI dry-run live échoué pour {scraper_name}",
            context=context_for_orchestrator_failure(
                scraper_name,
                source_id=official.source_id if official else None,
                error=output[-4000:],
                official_url=official.primary_url if official else "",
            ),
        )

    print(f"Enqueued {len(failed)} repair job(s)")
    return 0 if proc.returncode == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
