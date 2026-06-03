"""Spec orchestrateur barème indemnité kilométrique."""

from __future__ import annotations

from pathlib import Path

from core.rate_spec import PersistenceMode, RateSpec, ScraperScript

from _logic import (
    build_config_data,
    core_signature,
    equal_core,
    signature_for_emit,
    validate_signature,
)

_DIR = Path(__file__).resolve().parent

SPEC = RateSpec(
    scraper_name="bareme-indemnite-kilometrique",
    config_key="baremes_km",
    scripts=[
        ScraperScript(
            "bareme-indemnite-kilometrique.py",
            str(_DIR / "bareme-indemnite-kilometrique.py"),
            blocking=True,
        ),
        ScraperScript(
            "bareme-indemnite-kilometrique_AI.py",
            str(_DIR / "bareme-indemnite-kilometrique_AI.py"),
            blocking=False,
        ),
    ],
    extract_signature=core_signature,
    signatures_equal=equal_core,
    validate_signature=validate_signature,
    build_config_data=build_config_data,
    persistence_mode=PersistenceMode.FULL,
    comment="Mise à jour automatique: barème kilométrique",
    signature_for_emit=signature_for_emit,
)
