"""Spec orchestrateur frais professionnels."""

from __future__ import annotations

from pathlib import Path

from core.rate_spec import PersistenceMode, RateSpec, ScraperScript

from _logic import (
    accept_payload,
    build_config_data,
    core_signature,
    equal_core,
    validate_signature,
)

_DIR = Path(__file__).resolve().parent

SPEC = RateSpec(
    scraper_name="fraispro",
    config_key="frais_pro",
    scripts=[
        ScraperScript("fraispro.py", str(_DIR / "fraispro.py"), blocking=True),
        ScraperScript(
            "fraispro_AI.py",
            str(_DIR / "fraispro_AI.py"),
            blocking=False,
        ),
    ],
    extract_signature=core_signature,
    signatures_equal=equal_core,
    validate_signature=validate_signature,
    build_config_data=build_config_data,
    persistence_mode=PersistenceMode.FULL,
    primary_label="fraispro.py",
    accept_payload=accept_payload,
    signature_for_emit=lambda s: s,
)
