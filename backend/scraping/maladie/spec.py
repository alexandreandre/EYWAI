"""Spec MALADIE : CSG/CRDS sur indemnités journalières de Sécurité sociale (IJSS)."""

from __future__ import annotations

from pathlib import Path

from core.ai_scalar_spec import build_ai_scalar_spec

_DIR = Path(__file__).resolve().parent

SPEC = build_ai_scalar_spec(
    scraper_name="MALADIE",
    config_key="maladie",
    source_key="MALADIE",
    ai_script_path=str(_DIR / "maladie_AI.py"),
    keys=["csg_ijss_taux_deductible", "csg_ijss_taux_non_deductible"],
    bounds={
        "csg_ijss_taux_deductible": (0.0, 0.10),
        "csg_ijss_taux_non_deductible": (0.0, 0.10),
    },
    setters={
        "csg_ijss_taux_deductible": ["csg_ijss", "taux_deductible"],
        "csg_ijss_taux_non_deductible": ["csg_ijss", "taux_non_deductible"],
    },
    require_current=True,
    comment="Mise à jour automatique: CSG/CRDS sur IJSS (IA web)",
)
