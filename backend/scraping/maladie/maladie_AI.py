#!/usr/bin/env python3
"""Source IA — CSG/CRDS sur IJSS maladie (recherche web sourcée)."""
import sys
from pathlib import Path

_SCRAPING = Path(__file__).resolve().parent.parent
if str(_SCRAPING) not in sys.path:
    sys.path.insert(0, str(_SCRAPING))

from core.ai_scalar_source import run_ai_scalar_source  # noqa: E402

SCHEMA = {
    "type": "object",
    "properties": {
        "csg_ijss_taux_deductible": {"type": ["number", "null"]},
        "csg_ijss_taux_non_deductible": {"type": ["number", "null"]},
    },
    "required": ["csg_ijss_taux_deductible", "csg_ijss_taux_non_deductible"],
    "additionalProperties": False,
}

if __name__ == "__main__":
    run_ai_scalar_source(
        source_id="maladie",
        libelle="CSG/CRDS sur IJSS maladie",
        schema=SCHEMA,
        schema_name="maladie",
        keys=["csg_ijss_taux_deductible", "csg_ijss_taux_non_deductible"],
        generator="maladie/maladie_AI.py",
        task_prompt=(
            "CSG/CRDS applicables aux indemnités journalières de Sécurité "
            "sociale (IJSS) maladie en France : "
            "1) taux de CSG déductible, FRACTION (ex : 0.038). "
            "2) taux de CSG/CRDS non déductible, FRACTION (ex : 0.029). "
            "Sources officielles (BOSS, URSSAF)."
        ),
        label="BOSS/URSSAF — CSG/CRDS sur IJSS maladie (IA web)",
    )
