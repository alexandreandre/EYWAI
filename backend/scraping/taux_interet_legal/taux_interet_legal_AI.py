#!/usr/bin/env python3
"""Source IA — taux d'intérêt légal en vigueur (recherche web sourcée)."""
import sys
from pathlib import Path

_SCRAPING = Path(__file__).resolve().parent.parent
if str(_SCRAPING) not in sys.path:
    sys.path.insert(0, str(_SCRAPING))

from core.ai_scalar_source import run_ai_scalar_source  # noqa: E402

SCHEMA = {
    "type": "object",
    "properties": {"taux_annuel": {"type": ["number", "null"]}},
    "required": ["taux_annuel"],
    "additionalProperties": False,
}

if __name__ == "__main__":
    run_ai_scalar_source(
        source_id="taux_interet_legal",
        libelle="Taux d'intérêt légal",
        schema=SCHEMA,
        schema_name="taux_interet_legal",
        keys=["taux_annuel"],
        generator="taux_interet_legal/taux_interet_legal_AI.py",
        task_prompt=(
            "Taux d'intérêt légal EN VIGUEUR en France pour le semestre courant, "
            "cas général (créances entre professionnels / taux légal de référence). "
            "Réponds en FRACTION décimale annuelle (ex : 0.0526 pour 5,26 %). "
            "Sources officielles uniquement (Banque de France, service-public, "
            "Légifrance)."
        ),
        include_domains=[
            "banque-france.fr",
            "service-public.fr",
            "legifrance.gouv.fr",
        ],
        label="Banque de France — taux d'intérêt légal (IA web)",
    )
