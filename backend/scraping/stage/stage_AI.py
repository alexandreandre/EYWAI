#!/usr/bin/env python3
"""Source IA — gratification minimale de stage (recherche web sourcée)."""
import sys
from pathlib import Path

_SCRAPING = Path(__file__).resolve().parent.parent
if str(_SCRAPING) not in sys.path:
    sys.path.insert(0, str(_SCRAPING))

from core.ai_scalar_source import run_ai_scalar_source  # noqa: E402

SCHEMA = {
    "type": "object",
    "properties": {"pct_plafond_horaire_ss": {"type": ["number", "null"]}},
    "required": ["pct_plafond_horaire_ss"],
    "additionalProperties": False,
}

if __name__ == "__main__":
    run_ai_scalar_source(
        source_id="stage",
        libelle="Gratification minimale de stage",
        schema=SCHEMA,
        schema_name="stage",
        keys=["pct_plafond_horaire_ss"],
        generator="stage/stage_AI.py",
        task_prompt=(
            "Gratification minimale de stage en France : pourcentage du "
            "plafond horaire de la Sécurité sociale servant de base, en "
            "FRACTION (ex : 0.15 pour 15 %). "
            "Sources officielles (URSSAF, service-public)."
        ),
        label="Gratification de stage — pourcentage du plafond horaire SS (IA web)",
    )
