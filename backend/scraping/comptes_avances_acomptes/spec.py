"""Spec COMPTES_AVANCES_ACOMPTES : numéros de comptes PCG pour avances,
acomptes et banque (chaînes de chiffres, pas de valeur scalaire)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from core.ai_scalar_spec import build_ai_scalar_spec
from core.validation import ValidationResult

_DIR = Path(__file__).resolve().parent

_KEYS = ["avance", "acompte", "banque"]


def _validate(sig: Dict[str, Any]) -> ValidationResult:
    for key in _KEYS:
        val = sig.get(key)
        if val is None:
            continue
        if not isinstance(val, str) or not val.isdigit():
            return ValidationResult(
                False, f"{key} doit être une chaîne de chiffres (code PCG): {val!r}"
            )
    return ValidationResult(True)


def _build(sig: Dict[str, Any], current: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    cur = (current or {}).get("config_data") if current else None
    if not isinstance(cur, dict):
        raise ValueError("Config active requise pour un merge sûr")
    data = dict(cur)
    for key in _KEYS:
        val = sig.get(key)
        if val is None:
            continue
        data[key] = val
    return data


SPEC = build_ai_scalar_spec(
    scraper_name="COMPTES_AVANCES_ACOMPTES",
    config_key="comptes_avances_acomptes",
    source_key="COMPTES_AVANCES_ACOMPTES",
    ai_script_path=str(_DIR / "comptes_avances_acomptes_AI.py"),
    keys=_KEYS,
    setters={},
    validate=_validate,
    build=_build,
    comment="Mise à jour automatique: comptes PCG avances/acomptes/banque (IA web)",
)
