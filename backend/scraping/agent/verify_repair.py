"""Oracle machine : verify_repair() centralisé."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from agent.tools import (
    TestResult,
    run_compile_scraping,
    run_dry_run_all,
    run_dry_run_scraper,
    run_pytest_unit_scraping,
)

logger = logging.getLogger(__name__)


@dataclass
class VerifyResult:
    ok: bool
    stages: list[TestResult] = field(default_factory=list)
    message: str = ""


def verify_repair(scraper_name: str, *, full_gate: bool = False) -> VerifyResult:
    """
    Oracle automatisé post-patch.
    full_gate=True : compile + pytest + dry-run ciblé + dry-run 26 scrapers (merge).
    """
    stages: list[TestResult] = []

    compile_r = run_compile_scraping()
    stages.append(compile_r)
    if not compile_r.ok:
        return VerifyResult(False, stages, "Échec compilation scraping")

    pytest_r = run_pytest_unit_scraping()
    stages.append(pytest_r)
    if not pytest_r.ok:
        return VerifyResult(False, stages, "Échec tests unitaires scraping")

    dry_r = run_dry_run_scraper(scraper_name, live=True)
    stages.append(dry_r)
    if not dry_r.ok:
        return VerifyResult(False, stages, f"Dry-run live échoué pour {scraper_name}")

    if full_gate:
        all_r = run_dry_run_all()
        stages.append(all_r)
        if not all_r.ok:
            return VerifyResult(False, stages, "Dry-run complet (26 scrapers) échoué")

    return VerifyResult(True, stages, "Oracle OK")
