"""Spec orchestrateur PAS."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Optional

from core.rate_spec import PersistenceMode, RateSpec, ScraperScript
from core.validation import ValidationResult
from core.year_utils import current_year

_DIR = Path(__file__).resolve().parent


def _core_signature(payload: dict) -> dict:
    sections = payload.get("sections", {})
    baremes_list = []
    period = f"mensuel_{current_year()}"
    for zone, tranches in sections.items():
        if isinstance(tranches, list):
            tranches = sorted(
                tranches,
                key=lambda x: float("inf") if x.get("plafond") is None else x["plafond"],
            )
            baremes_list.append(
                {"periode": period, "zone": zone, "tranches": tranches}
            )
    baremes_list.sort(key=lambda x: x["zone"])
    return {"baremes": baremes_list}


def _equal(a: dict, b: dict) -> bool:
    ba, bb = a.get("baremes", []), b.get("baremes", [])
    if len(ba) != len(bb):
        return False
    for za, zb in zip(ba, bb):
        if za.get("zone") != zb.get("zone"):
            return False
        ta, tb = za.get("tranches", []), zb.get("tranches", [])
        if len(ta) != len(tb):
            return False
        for xa, xb in zip(ta, tb):
            pa, pb = xa.get("plafond"), xb.get("plafond")
            if pa is None and pb is None:
                pass
            elif pa is None or pb is None:
                return False
            elif not math.isclose(float(pa), float(pb), abs_tol=1e-6):
                return False
            if not math.isclose(float(xa["taux"]), float(xb["taux"]), abs_tol=1e-6):
                return False
    return True


def _validate(sig: dict) -> ValidationResult:
    if not sig.get("baremes"):
        return ValidationResult(False, "barèmes PAS vides")
    return ValidationResult(True)


SPEC = RateSpec(
    scraper_name="PAS",
    config_key="pas",
    scripts=[
        ScraperScript("PAS.py", str(_DIR / "PAS.py"), blocking=True),
        ScraperScript("PAS_AI.py", str(_DIR / "PAS_AI.py"), blocking=False),
    ],
    extract_signature=_core_signature,
    signatures_equal=_equal,
    validate_signature=_validate,
    build_config_data=lambda sig, _c: sig,
    persistence_mode=PersistenceMode.FULL,
    primary_label="PAS.py",
)
