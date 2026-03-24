"""
Value objects du domaine scraping.

Représentations typées des identifiants et valeurs métier.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class SourceKey:
    """Clé unique d'une source de scraping (ex: SMIC, PSS, AGIRC-ARRCO)."""

    value: str


@dataclass(frozen=True)
class ScraperScriptType:
    """Type de script exécuté : orchestrator ou single_scraper."""

    value: str  # "orchestrator" | "single_scraper"
