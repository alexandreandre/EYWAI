"""Spec orchestrateur primes (catalogue statique)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from core.rate_spec import PersistenceMode, RateSpec, ScraperScript
from core.validation import ValidationResult

_DIR = Path(__file__).resolve().parent


def _load_catalogue() -> dict:
    path = _DIR / "primes.py"
    spec = importlib.util.spec_from_file_location("primes_catalogue", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod.CATALOGUE


CATALOGUE = _load_catalogue()


def _extract(p: dict) -> dict:
    primes = p.get("config_data", {}).get("primes") or []
    return {
        item["id"]: {
            "soumise_a_impot": item.get("soumise_a_impot"),
            "soumise_a_cotisations": item.get("soumise_a_cotisations"),
        }
        for item in primes
        if isinstance(item, dict) and item.get("id")
    }


SPEC = RateSpec(
    scraper_name="PRIMES",
    config_key="primes",
    scripts=[
        ScraperScript("primes.py", str(_DIR / "primes.py"), blocking=True),
        ScraperScript("primes_AI.py", str(_DIR / "primes_AI.py"), blocking=False),
    ],
    extract_signature=_extract,
    signatures_equal=lambda a, b: a == b,
    validate_signature=lambda s: ValidationResult(
        len(s) >= 3, "catalogue primes incomplet" if len(s) < 3 else ""
    ),
    build_config_data=lambda _s, _c: CATALOGUE,
    persistence_mode=PersistenceMode.FULL,
    primary_label="primes.py",
)
