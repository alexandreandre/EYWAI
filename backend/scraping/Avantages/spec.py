"""Spec orchestrateur avantages en nature."""

from __future__ import annotations

from pathlib import Path

from core.rate_spec import PersistenceMode, RateSpec, ScraperScript

from _logic import (
    build_config_data,
    cores_equal,
    payload_to_core,
    signature_for_emit,
    validate_signature,
)

_DIR = Path(__file__).resolve().parent

SPEC = RateSpec(
    scraper_name="Avantages",
    config_key="avantages_en_nature",
    scripts=[
        ScraperScript("URSSAF", str(_DIR / "Avantages.py"), blocking=True),
        ScraperScript(
            "Avantages_AI.py",
            str(_DIR / "Avantages_AI.py"),
            blocking=False,
        ),
    ],
    extract_signature=payload_to_core,
    signatures_equal=cores_equal,
    validate_signature=validate_signature,
    build_config_data=build_config_data,
    persistence_mode=PersistenceMode.FULL,
    primary_label="URSSAF",
    signature_for_emit=signature_for_emit,
)
