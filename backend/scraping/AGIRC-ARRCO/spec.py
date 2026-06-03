"""Spec orchestrateur AGIRC-ARRCO."""

from __future__ import annotations

from pathlib import Path

from core.rate_spec import PersistenceMode, RateSpec, ScraperScript

from _logic import (
    ITEMS_ID_TO_PATCH,
    accept_payload,
    build_config_data,
    bundles_pair_equal,
    core_signature,
    validate_signature,
)

_DIR = Path(__file__).resolve().parent

SPEC = RateSpec(
    scraper_name="AGIRC-ARRCO",
    config_key="cotisations",
    scripts=[
        ScraperScript("AGIRC-ARRCO.py", str(_DIR / "AGIRC-ARRCO.py"), blocking=True),
        ScraperScript(
            "AGIRC-ARRCO_AI.py",
            str(_DIR / "AGIRC-ARRCO_AI.py"),
            blocking=False,
        ),
    ],
    extract_signature=core_signature,
    signatures_equal=bundles_pair_equal,
    validate_signature=validate_signature,
    build_config_data=build_config_data,
    persistence_mode=PersistenceMode.COTISATIONS,
    comment=f"Mise à jour automatique: AGIRC-ARRCO ({', '.join(ITEMS_ID_TO_PATCH)})",
    primary_label="AGIRC-ARRCO.py",
    accept_payload=accept_payload,
    signature_for_emit=lambda s: s,
)
