"""Spécification orchestrateur dialogue social."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Optional

from core.cotisation_helpers import patch_cotisation_fields, payload_sections
from core.rate_spec import PersistenceMode, RateSpec, ScraperScript
from core.validation import validate_dialogue_social, ValidationResult

_DIR = Path(__file__).resolve().parent
ITEM_ID = "dialogue_social"


def _extract_sig(payload: dict) -> dict:
    v = payload.get("valeurs") or payload_sections(payload)
    return {"valeurs": {"salarial": v.get("salarial"), "patronal": v.get("patronal")}}


def _equal(a: dict, b: dict) -> bool:
    pa = a["valeurs"].get("patronal")
    pb = b["valeurs"].get("patronal")
    if pa is None or pb is None:
        return pa is pb
    return math.isclose(float(pa), float(pb), abs_tol=1e-9)


def _validate(sig: dict) -> ValidationResult:
    return validate_dialogue_social(sig["valeurs"])


def _build(sig: dict, current: Optional[dict]) -> dict:
    pat = sig["valeurs"]["patronal"]
    cur = current["config_data"] if current else None
    return patch_cotisation_fields(
        cur,
        patches=[(ITEM_ID, {"patronal": pat, "salarial": None})],
        default_new_items={
            ITEM_ID: {
                "id": ITEM_ID,
                "libelle": "Contribution au dialogue social",
                "base": "brut",
                "salarial": None,
            }
        },
    )


SPEC = RateSpec(
    scraper_name="dialoguesocial",
    config_key="cotisations",
    scripts=[
        ScraperScript("dialoguesocial.py", str(_DIR / "dialoguesocial.py"), blocking=True),
        ScraperScript(
            "dialoguesocial_AI.py",
            str(_DIR / "dialoguesocial_AI.py"),
            blocking=False,
        ),
    ],
    extract_signature=_extract_sig,
    signatures_equal=_equal,
    validate_signature=_validate,
    build_config_data=_build,
    persistence_mode=PersistenceMode.COTISATIONS,
    comment=f"Mise à jour automatique: {ITEM_ID}",
    primary_label="dialoguesocial.py",
    signature_for_emit=lambda s: s["valeurs"],
)
