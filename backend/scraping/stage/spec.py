"""Spec STAGE : gratification minimale de stage (fraction du plafond horaire SS)."""

from __future__ import annotations

from pathlib import Path

from core.ai_scalar_spec import build_ai_scalar_spec

_DIR = Path(__file__).resolve().parent

SPEC = build_ai_scalar_spec(
    scraper_name="STAGE",
    config_key="stage",
    source_key="STAGE",
    ai_script_path=str(_DIR / "stage_AI.py"),
    keys=["pct_plafond_horaire_ss"],
    bounds={"pct_plafond_horaire_ss": (0.10, 0.20)},
    setters={"pct_plafond_horaire_ss": ["pct_plafond_horaire_ss"]},
    require_current=False,  # config plate simple : création sûre
    comment="Mise à jour automatique: gratification de stage (IA web)",
)
