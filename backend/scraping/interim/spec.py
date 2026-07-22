"""Spec INTERIM : indemnité de fin de mission + indemnité compensatrice de congés payés."""

from __future__ import annotations

from pathlib import Path

from core.ai_scalar_spec import build_ai_scalar_spec

_DIR = Path(__file__).resolve().parent

SPEC = build_ai_scalar_spec(
    scraper_name="INTERIM",
    config_key="interim",
    source_key="INTERIM",
    ai_script_path=str(_DIR / "interim_AI.py"),
    keys=["ifm_taux", "indemnite_conges_taux"],
    bounds={
        "ifm_taux": (0.0, 0.15),
        "indemnite_conges_taux": (0.08, 0.12),
    },
    setters={
        "ifm_taux": ["ifm", "taux"],
        "indemnite_conges_taux": ["indemnite_conges", "taux"],
    },
    require_current=True,
    comment="Mise à jour automatique: taux intérim (IFM, ICCP) (IA web)",
)
