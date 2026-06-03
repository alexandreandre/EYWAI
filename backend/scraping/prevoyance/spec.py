"""Specs orchestrateurs prévoyance cadre et non-cadre."""

from __future__ import annotations

from pathlib import Path

from core.rate_spec import PersistenceMode, RateSpec, ScraperScript

from _logic import (
    accept_payload,
    build_config_data,
    equal_branch,
    make_extract,
    validate_cadre,
    validate_non_cadre,
)

_DIR = Path(__file__).resolve().parent
_SCRIPT = ScraperScript("prevoyance.py", str(_DIR / "prevoyance.py"), blocking=True)

PREVOYANCE_CADRE = RateSpec(
    scraper_name="PREVOYANCE_CADRE",
    config_key="cotisations",
    scripts=[_SCRIPT],
    extract_signature=make_extract("cadre", "prevoyance_cadre"),
    signatures_equal=equal_branch,
    validate_signature=validate_cadre,
    build_config_data=build_config_data("prevoyance_cadre"),
    persistence_mode=PersistenceMode.COTISATIONS,
    comment="Mise à jour automatique: prevoyance_cadre",
    accept_payload=accept_payload("cadre"),
    warn_single_source=True,
    dual_source_consensus=False,
)

PREVOYANCE_NON_CADRE = RateSpec(
    scraper_name="PREVOYANCE_NON_CADRE",
    config_key="cotisations",
    scripts=[_SCRIPT],
    extract_signature=make_extract("non_cadre", "prevoyance_non_cadre"),
    signatures_equal=equal_branch,
    validate_signature=validate_non_cadre,
    build_config_data=build_config_data("prevoyance_non_cadre"),
    persistence_mode=PersistenceMode.COTISATIONS,
    comment="Mise à jour automatique: prevoyance_non_cadre",
    accept_payload=accept_payload("non_cadre"),
    warn_single_source=True,
    dual_source_consensus=False,
)
