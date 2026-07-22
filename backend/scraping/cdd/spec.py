"""Spec CDD : prime de précarité + indemnité compensatrice de congés payés."""

from __future__ import annotations

from pathlib import Path

from core.ai_scalar_spec import build_ai_scalar_spec

_DIR = Path(__file__).resolve().parent

SPEC = build_ai_scalar_spec(
    scraper_name="CDD",
    config_key="cdd",
    source_key="CDD",
    ai_script_path=str(_DIR / "cdd_AI.py"),
    keys=["precarite_taux", "indemnite_conges_taux"],
    bounds={
        "precarite_taux": (0.0, 0.15),
        "indemnite_conges_taux": (0.08, 0.12),
    },
    setters={
        "precarite_taux": ["precarite", "taux"],
        "indemnite_conges_taux": ["indemnite_conges", "taux"],
    },
    require_current=True,  # préserve precarite.actif
    comment="Mise à jour automatique: taux CDD (précarité, ICCP) (IA web)",
)
