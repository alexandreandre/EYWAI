"""Spécification orchestrateur SMIC."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from core.cotisation_helpers import equal_sections_keys
from core.rate_spec import PersistenceMode, RateSpec, ScraperScript
from core.validation import (
    normalize_smic_sections,
    smic_hourly_rate,
    validate_smic_sections,
    ValidationResult,
)

_DIR = Path(__file__).resolve().parent


def _extract_sig(payload: dict) -> dict:
    sections = payload.get("sections", {})
    skip = {"effective_from", "source"}
    raw = {
        k: v
        for k, v in sections.items()
        if k not in skip and (k != "annee" or v is not None)
    }
    return normalize_smic_sections(raw)


def _equal(a: dict, b: dict) -> bool:
    a_n = normalize_smic_sections(a)
    b_n = normalize_smic_sections(b)
    if not equal_sections_keys(
        {"h": smic_hourly_rate(a_n)},
        {"h": smic_hourly_rate(b_n)},
        ["h"],
        abs_tol=0.01,
    ):
        return False
    for key in ("jeune_17_ans", "jeune_moins_17_ans", "smic_mensuel_brut"):
        va, vb = a_n.get(key), b_n.get(key)
        if va is None and vb is None:
            continue
        if not equal_sections_keys({key: va}, {key: vb}, [key], abs_tol=0.02):
            return False
    return True


def _validate(sig: dict) -> ValidationResult:
    full = {**sig}
    if "annee" not in full:
        from core.year_utils import current_year

        full["annee"] = current_year()
    return validate_smic_sections(full)


def _build(sig: dict, _current: Optional[dict]) -> dict:
    from core.year_utils import current_year

    out = normalize_smic_sections(
        {
            k: v
            for k, v in sig.items()
            if k not in ("smic_horaire", "effective_from", "source")
        }
    )
    out["annee"] = current_year()
    return out


SPEC = RateSpec(
    scraper_name="SMIC",
    config_key="smic",
    scripts=[
        ScraperScript("SMIC.py", str(_DIR / "SMIC.py"), blocking=True),
        ScraperScript("SMIC_AI.py", str(_DIR / "SMIC_AI.py"), blocking=False),
    ],
    extract_signature=_extract_sig,
    signatures_equal=_equal,
    validate_signature=_validate,
    build_config_data=_build,
    persistence_mode=PersistenceMode.FULL,
    comment="Mise à jour automatique: smic",
    primary_label="SMIC.py",
    script_timeout=180,
)
