"""Spec MANDATAIRE : cotisations exclues pour un dirigeant/mandataire social
assimilé salarié (liste, pas de valeur scalaire)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from core.ai_scalar_spec import build_ai_scalar_spec
from core.validation import ValidationResult

_DIR = Path(__file__).resolve().parent

_COTISATIONS_CONNUES = {"assurance_chomage", "ags", "chomage", "apec"}


def _validate(sig: Dict[str, Any]) -> ValidationResult:
    valeurs = sig.get("cotisations_exclues")
    if not isinstance(valeurs, list):
        return ValidationResult(False, "cotisations_exclues doit être une liste")
    inconnues = [v for v in valeurs if v not in _COTISATIONS_CONNUES]
    if inconnues:
        return ValidationResult(
            False, f"cotisations_exclues contient des valeurs inconnues: {inconnues!r}"
        )
    return ValidationResult(True)


def _build(sig: Dict[str, Any], current: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    cur = (current or {}).get("config_data") if current else None
    if not isinstance(cur, dict):
        raise ValueError("Config active requise pour un merge sûr")
    data = dict(cur)
    data["cotisations_exclues"] = sig.get("cotisations_exclues")
    return data


SPEC = build_ai_scalar_spec(
    scraper_name="MANDATAIRE",
    config_key="mandataire",
    source_key="MANDATAIRE",
    ai_script_path=str(_DIR / "mandataire_AI.py"),
    keys=["cotisations_exclues"],
    setters={},
    validate=_validate,
    build=_build,
    comment="Mise à jour automatique: cotisations exclues (mandataire social) (IA web)",
)
