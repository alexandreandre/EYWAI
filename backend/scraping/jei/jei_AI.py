#!/usr/bin/env python3
"""Source IA — plafond d'exonération JEI (recherche web sourcée)."""
import sys
from pathlib import Path

_SCRAPING = Path(__file__).resolve().parent.parent
if str(_SCRAPING) not in sys.path:
    sys.path.insert(0, str(_SCRAPING))

from core.ai_scalar_source import run_ai_scalar_source  # noqa: E402

SCHEMA = {
    "type": "object",
    "properties": {"facteur_smic_plafond": {"type": ["number", "null"]}},
    "required": ["facteur_smic_plafond"],
    "additionalProperties": False,
}

if __name__ == "__main__":
    run_ai_scalar_source(
        source_id="jei",
        libelle="Plafond d'exonération JEI",
        schema=SCHEMA,
        schema_name="jei",
        keys=["facteur_smic_plafond"],
        generator="jei/jei_AI.py",
        task_prompt=(
            "Jeune Entreprise Innovante (JEI) en France, exonération de "
            "cotisations patronales : plafond de rémunération mensuelle "
            "exonérée exprimé en MULTIPLE du SMIC (ex : 4.5). "
            "Sources officielles (BOSS, URSSAF)."
        ),
        label="BOSS/URSSAF — plafond exonération JEI (IA web)",
    )
