#!/usr/bin/env python3
"""Source IA — comptes PCG avances/acomptes/banque (recherche web sourcée)."""
import sys
from pathlib import Path

_SCRAPING = Path(__file__).resolve().parent.parent
if str(_SCRAPING) not in sys.path:
    sys.path.insert(0, str(_SCRAPING))

from core.ai_scalar_source import run_ai_scalar_source  # noqa: E402

SCHEMA = {
    "type": "object",
    "properties": {
        "avance": {"type": ["string", "null"]},
        "acompte": {"type": ["string", "null"]},
        "banque": {"type": ["string", "null"]},
    },
    "additionalProperties": False,
}

if __name__ == "__main__":
    run_ai_scalar_source(
        source_id="comptes_avances_acomptes",
        libelle="Comptes PCG (avances, acomptes, banque)",
        schema=SCHEMA,
        schema_name="comptes_avances_acomptes",
        keys=["avance", "acompte", "banque"],
        generator="comptes_avances_acomptes/comptes_avances_acomptes_AI.py",
        task_prompt=(
            "Plan Comptable Général français : numéro de compte standard pour "
            "1) avances au personnel (avance), 2) acomptes au personnel (acompte), "
            "3) banque (banque). "
            'Réponds par les codes PCG (ex : "425","425","512").'
        ),
        label="PCG — comptes avances/acomptes/banque (IA web)",
    )
