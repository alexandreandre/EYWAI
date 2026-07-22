"""Spec orchestrateur ALTERNANCE (régime apprenti).

Source mono (IA web sourcée) : la valeur est réglementaire/prose, sans tableau
officiel scrappable de façon déterministe. La sécurité vient du tier « critical »
(revue humaine avant toute écriture d'un changement) et d'un build qui FUSIONNE
sans jamais reconstruire la structure du bloc alternance.
"""

from __future__ import annotations

from pathlib import Path

from core.rate_spec import PersistenceMode, RateSpec, ScraperScript

from _logic import (
    build_config_data,
    core_signature,
    signature_for_emit,
    signatures_equal,
    validate_signature,
)

_DIR = Path(__file__).resolve().parent

SPEC = RateSpec(
    scraper_name="ALTERNANCE",
    config_key="alternance",
    scripts=[
        ScraperScript(
            "alternance_AI.py",
            str(_DIR / "alternance_AI.py"),
            blocking=True,
        ),
    ],
    extract_signature=core_signature,
    signatures_equal=signatures_equal,
    validate_signature=validate_signature,
    build_config_data=build_config_data,
    persistence_mode=PersistenceMode.FULL,
    comment="Mise à jour automatique: régime alternance (apprenti)",
    primary_label="alternance_AI.py",
    dual_source_consensus=False,
    warn_single_source=True,
    signature_for_emit=signature_for_emit,
    source_key="ALTERNANCE",
    tier="critical",
)
