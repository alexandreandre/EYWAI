#!/usr/bin/env python3
"""Source IA — cotisations exclues pour un dirigeant/mandataire social
(recherche web sourcée)."""
import sys
from pathlib import Path

_SCRAPING = Path(__file__).resolve().parent.parent
if str(_SCRAPING) not in sys.path:
    sys.path.insert(0, str(_SCRAPING))

from core.ai_scalar_source import run_ai_scalar_source  # noqa: E402

SCHEMA = {
    "type": "object",
    "properties": {
        "cotisations_exclues": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["cotisations_exclues"],
    "additionalProperties": False,
}

if __name__ == "__main__":
    run_ai_scalar_source(
        source_id="mandataire",
        libelle="Cotisations exclues (mandataire social)",
        schema=SCHEMA,
        schema_name="mandataire",
        keys=["cotisations_exclues"],
        generator="mandataire/mandataire_AI.py",
        task_prompt=(
            "Dirigeant/mandataire social assimilé salarié en France : "
            "liste des cotisations dont il est EXCLU (identifiants attendus "
            "parmi : assurance_chomage, ags, chomage, apec). "
            "Sources officielles (URSSAF, BOSS)."
        ),
        label="Mandataire social — cotisations exclues (IA web)",
    )
