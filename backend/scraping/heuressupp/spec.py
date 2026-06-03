"""Spec orchestrateur heures supplémentaires."""

from __future__ import annotations

import copy
import math
from pathlib import Path
from typing import Any, Dict, Optional

from core.rate_spec import PersistenceMode, RateSpec, ScraperScript
from core.validation import ValidationResult, require_float_range

_DIR = Path(__file__).resolve().parent


def _to_float(x: Any) -> float | None:
    if x is None:
        return None
    try:
        if isinstance(x, str):
            x = x.replace("\u202f", "").replace("\xa0", "").replace(",", ".")
        return float(x)
    except (ValueError, TypeError):
        return None


def payload_to_core(payload: dict) -> dict[str, float]:
    mp = {
        it.get("key"): it.get("value")
        for it in payload.get("items", [])
        if isinstance(it, dict)
    }
    return {
        "majoration_hs_25": _to_float(mp.get("majoration_hs_25")),
        "majoration_hs_50": _to_float(mp.get("majoration_hs_50")),
        "reduction_plafond_legal": _to_float(mp.get("reduction_plafond_legal")),
        "deduction_effectif_1_19": _to_float(mp.get("deduction_effectif_1_19")),
        "deduction_effectif_20_249": _to_float(mp.get("deduction_effectif_20_249")),
    }


def apply_core_to_config(config_data: dict, core: dict[str, float]) -> dict:
    patched = copy.deepcopy(config_data)
    rc = patched.setdefault("regles_calcul_communes", {})
    taux = rc.setdefault("taux_majoration_par_defaut", {})
    hs_list = list(taux.get("heures_supplementaires") or [{}, {}])
    while len(hs_list) < 2:
        hs_list.append({})
    hs_list[0]["taux"] = core["majoration_hs_25"]
    hs_list[1]["taux"] = core["majoration_hs_50"]
    taux["heures_supplementaires"] = hs_list

    red = patched.setdefault("reduction_salariale", {})
    taux_red = red.setdefault("taux_reduction", {})
    taux_red["plafond_legal"] = core["reduction_plafond_legal"]

    ded = patched.setdefault("deduction_patronale", {})
    paliers = list(ded.get("montants_forfaitaires") or [{}, {}])
    while len(paliers) < 2:
        paliers.append({})
    paliers[0]["montant_par_heure_sup_eur"] = core["deduction_effectif_1_19"]
    paliers[1]["montant_par_heure_sup_eur"] = core["deduction_effectif_20_249"]
    ded["montants_forfaitaires"] = paliers
    return patched


def _validate(sig: dict) -> ValidationResult:
    for k, lo, hi in [
        ("majoration_hs_25", 0.1, 0.5),
        ("majoration_hs_50", 0.3, 0.8),
        ("reduction_plafond_legal", 0.05, 0.2),
        ("deduction_effectif_1_19", 0.5, 3.0),
        ("deduction_effectif_20_249", 0.1, 2.0),
    ]:
        r = require_float_range(sig.get(k), name=k, min_v=lo, max_v=hi)
        if not r.ok:
            return r
    return ValidationResult(True)


def _build(sig: dict, current: Optional[dict]) -> dict:
    if current and current.get("config_data"):
        return apply_core_to_config(current["config_data"], sig)
    return apply_core_to_config({}, sig)


SPEC = RateSpec(
    scraper_name="HEURES_SUPP",
    config_key="heures_supp",
    scripts=[
        ScraperScript("heuressupp.py", str(_DIR / "heuressupp.py"), blocking=True),
        ScraperScript(
            "heuressupp_AI.py",
            str(_DIR / "heuressupp_AI.py"),
            blocking=False,
        ),
    ],
    extract_signature=payload_to_core,
    signatures_equal=lambda a, b: all(
        math.isclose(float(a[k]), float(b[k]), abs_tol=1e-6)
        for k in a
        if a.get(k) is not None
    ),
    validate_signature=_validate,
    build_config_data=_build,
    persistence_mode=PersistenceMode.FULL,
    primary_label="heuressupp.py",
)
