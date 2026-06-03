"""Alertes métier émises par les orchestrateurs (logs + JSON)."""

from __future__ import annotations

import logging
from typing import List

logger = logging.getLogger("scraping.alerts")


def emit_scraping_warnings(
    scraper_name: str,
    warnings: List[str],
    *,
    single_source: bool = False,
    primary_failed: bool = False,
) -> None:
    for w in warnings:
        logger.warning("[%s] %s", scraper_name, w)
    if single_source:
        logger.warning(
            "[%s] ALERTE: consensus sur une seule source — fiabilité réduite",
            scraper_name,
        )
    if primary_failed:
        logger.error(
            "[%s] ALERTE: source officielle primaire en échec",
            scraper_name,
        )
