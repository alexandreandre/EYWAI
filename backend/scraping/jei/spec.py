"""Spec JEI : plafond d'exonération de cotisations patronales (Jeune Entreprise Innovante)."""

from __future__ import annotations

from pathlib import Path

from core.ai_scalar_spec import build_ai_scalar_spec

_DIR = Path(__file__).resolve().parent

SPEC = build_ai_scalar_spec(
    scraper_name="JEI",
    config_key="jei",
    source_key="JEI",
    ai_script_path=str(_DIR / "jei_AI.py"),
    keys=["facteur_smic_plafond"],
    bounds={"facteur_smic_plafond": (3.0, 6.0)},
    setters={"facteur_smic_plafond": ["facteur_smic_plafond"]},
    require_current=True,  # préserve actif, cotisations_exonerees_patronales
    comment="Mise à jour automatique: plafond exonération JEI (IA web)",
)
