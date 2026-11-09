"""Spec REDUCTION_GENERALE : paramètres de la réduction générale dégressive (RGDU)."""

from __future__ import annotations

from pathlib import Path

from core.ai_scalar_spec import build_ai_scalar_spec

_DIR = Path(__file__).resolve().parent

SPEC = build_ai_scalar_spec(
    scraper_name="REDUCTION_GENERALE",
    config_key="reduction_generale",
    source_key="REDUCTION_GENERALE",
    ai_script_path=str(_DIR / "reduction_generale_AI.py"),
    keys=[
        "tmin",
        "p",
        "point_sortie_smic",
        "tdelta_fnal_moins_50",
        "tdelta_fnal_50_et_plus",
    ],
    bounds={
        # Bornes resserrées (R-265) : en 2026, Tmin 0,02, Tdelta 0,3781 / 0,3821.
        # Tmax (0,3981 / 0,4021) ne peut plus passer pour Tdelta.
        "tmin": (0.015, 0.03),
        "p": (1.0, 3.0),
        "point_sortie_smic": (1.6, 4.0),
        "tdelta_fnal_moins_50": (0.35, 0.39),
        "tdelta_fnal_50_et_plus": (0.35, 0.39),
    },
    setters={
        "tmin": ["tmin"],
        "p": ["p"],
        "point_sortie_smic": ["point_sortie_smic"],
        "tdelta_fnal_moins_50": ["tdelta", "fnal_moins_50"],
        "tdelta_fnal_50_et_plus": ["tdelta", "fnal_50_et_plus"],
    },
    require_current=True,  # préserve actif
    comment="Mise à jour automatique: paramètres RGDU (IA web)",
)
