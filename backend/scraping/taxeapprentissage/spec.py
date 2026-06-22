"""Spec orchestrateur taxe d'apprentissage."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from core.cotisation_helpers import patch_cotisation_fields
from core.rate_spec import PersistenceMode, RateSpec, ScraperScript
from core.validation import ValidationResult

_DIR = Path(__file__).resolve().parent


def _extract(p: dict) -> dict:
    return p.get("sections", {})


def _cmp_float(a: Any, b: Any, tol: float = 1e-6) -> bool:
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    return abs(float(a) - float(b)) <= tol


def _equal(a: dict, b: dict) -> bool:
    for section in ("part_principale", "solde"):
        sa, sb = a.get(section) or {}, b.get(section) or {}
        for k in ("taux_metropole", "taux_alsace_moselle"):
            if not _cmp_float(sa.get(k), sb.get(k)):
                return False
    return True


def _validate(sig: dict) -> ValidationResult:
    pp = sig.get("part_principale") or {}
    if pp.get("taux_metropole") is None:
        return ValidationResult(False, "part principale manquante")
    return ValidationResult(True)


def _build(sig: dict, current: Optional[dict]) -> dict:
    cur = current["config_data"] if current else None
    pp = sig.get("part_principale") or {}
    sol = sig.get("solde") or {}
    data = patch_cotisation_fields(
        cur,
        patches=[
            (
                "taxe_apprentissage",
                {
                    "patronal": {
                        "taux_metropole": pp.get("taux_metropole"),
                        "taux_alsace_moselle": pp.get("taux_alsace_moselle"),
                    }
                },
            ),
            (
                "taxe_apprentissage_solde",
                {
                    "patronal": {
                        "taux_metropole": sol.get("taux_metropole"),
                        "taux_alsace_moselle": sol.get("taux_alsace_moselle"),
                    }
                },
            ),
        ],
        default_new_items={
            "taxe_apprentissage": {
                "id": "taxe_apprentissage",
                "libelle": "Taxe d'apprentissage — part principale",
                "base": "brut",
            },
            "taxe_apprentissage_solde": {
                "id": "taxe_apprentissage_solde",
                "libelle": "Taxe d'apprentissage — solde",
                "base": "brut",
            },
        },
    )
    return data


SPEC = RateSpec(
    scraper_name="taxeapprentissage",
    config_key="cotisations",
    scripts=[
        ScraperScript("taxeapprentissage.py", str(_DIR / "taxeapprentissage.py"), blocking=True),
        ScraperScript(
            "taxeapprentissage_AI.py",
            str(_DIR / "taxeapprentissage_AI.py"),
            blocking=False,
        ),
    ],
    extract_signature=_extract,
    signatures_equal=_equal,
    validate_signature=_validate,
    build_config_data=_build,
    persistence_mode=PersistenceMode.COTISATIONS,
    primary_label="taxeapprentissage.py",
)
