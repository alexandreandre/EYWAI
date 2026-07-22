#!/usr/bin/env python3
"""Source IA — taux d'obligation d'emploi OETH (recherche web sourcée)."""
import sys
from pathlib import Path

_SCRAPING = Path(__file__).resolve().parent.parent
if str(_SCRAPING) not in sys.path:
    sys.path.insert(0, str(_SCRAPING))

from core.ai_scalar_source import run_ai_scalar_source  # noqa: E402

SCHEMA = {
    "type": "object",
    "properties": {"taux_obligation": {"type": ["number", "null"]}},
    "required": ["taux_obligation"],
    "additionalProperties": False,
}

if __name__ == "__main__":
    run_ai_scalar_source(
        source_id="oeth",
        libelle="Taux d'obligation d'emploi OETH",
        schema=SCHEMA,
        schema_name="oeth",
        keys=["taux_obligation"],
        generator="oeth/oeth_AI.py",
        task_prompt=(
            "Obligation d'emploi des travailleurs handicapés (OETH/DOETH) "
            "en France : taux légal d'obligation d'emploi, en FRACTION "
            "(ex : 0.06 pour 6 %). Sources officielles (URSSAF, "
            "service-public)."
        ),
        label="URSSAF/service-public — taux OETH (IA web)",
    )
