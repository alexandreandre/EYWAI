"""Spec TAUX_INTERET_LEGAL : taux d'intérêt légal annuel en vigueur (fraction)."""

from __future__ import annotations

from pathlib import Path

from core.ai_scalar_spec import build_ai_scalar_spec

_DIR = Path(__file__).resolve().parent

SPEC = build_ai_scalar_spec(
    scraper_name="TAUX_INTERET_LEGAL",
    config_key="taux_interet_legal",
    source_key="TAUX_INTERET_LEGAL",
    ai_script_path=str(_DIR / "taux_interet_legal_AI.py"),
    keys=["taux_annuel"],
    bounds={"taux_annuel": (0.0, 0.20)},
    setters={"taux_annuel": ["taux_annuel"]},
    require_current=False,  # config plate simple : création sûre
    comment="Mise à jour automatique: taux d'intérêt légal (IA web)",
)
