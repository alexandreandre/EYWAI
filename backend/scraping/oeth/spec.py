"""Spec OETH : taux légal d'obligation d'emploi des travailleurs handicapés."""

from __future__ import annotations

from pathlib import Path

from core.ai_scalar_spec import build_ai_scalar_spec

_DIR = Path(__file__).resolve().parent

SPEC = build_ai_scalar_spec(
    scraper_name="OETH",
    config_key="oeth",
    source_key="OETH",
    ai_script_path=str(_DIR / "oeth_AI.py"),
    keys=["taux_obligation"],
    bounds={"taux_obligation": (0.0, 0.10)},
    setters={"taux_obligation": ["taux_obligation"]},
    require_current=True,  # préserve coefficients, boeth_50_plus_factor, etc.
    comment="Mise à jour automatique: taux OETH (IA web)",
)
