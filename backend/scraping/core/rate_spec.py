"""Spécification déclarative d'un taux à scraper."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

from core.validation import ValidationResult


class PersistenceMode(str, Enum):
    FULL = "full"
    COTISATIONS = "cotisations"


@dataclass
class ScraperScript:
    label: str
    path: str
    enabled: bool = True
    blocking: bool = False  # False = secondaire / IA non bloquant


@dataclass
class RateSpec:
    """Configuration d'un orchestrateur de taux."""

    scraper_name: str
    config_key: str
    scripts: List[ScraperScript]
    extract_signature: Callable[[Dict[str, Any]], Any]
    signatures_equal: Callable[[Any, Any], bool]
    validate_signature: Callable[[Any], ValidationResult]
    build_config_data: Callable[[Any, Optional[Dict[str, Any]]], Dict[str, Any]]
    persistence_mode: PersistenceMode = PersistenceMode.FULL
    comment: str = ""
    primary_label: Optional[str] = None
    script_timeout: int = 120
    accept_payload: Optional[Callable[[str, Dict[str, Any]], bool]] = None
    signature_for_emit: Optional[Callable[[Any], Dict[str, Any]]] = None
    warn_single_source: bool = True
    # True : scraper (primary) + Sonar doivent concorder — pas d'écriture sinon.
    dual_source_consensus: bool = True
    # Tier de criticité (None = résolu via scraper_manifest.tier_for au runtime).
    tier: Optional[str] = None
    # source_key Supabase (scraping_sources) si différent de scraper_name.
    source_key: Optional[str] = None

    def script_tuples(self) -> List[Tuple[str, str]]:
        return [(s.label, s.path) for s in self.scripts if s.enabled]

    def has_ai_script(self) -> bool:
        from utils import is_ai_scraper_label

        return any(
            s.enabled and is_ai_scraper_label(s.label) for s in self.scripts
        )

    def requires_scraper_sonar_consensus(self) -> bool:
        return self.dual_source_consensus and self.has_ai_script()
