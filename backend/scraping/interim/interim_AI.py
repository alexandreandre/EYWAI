#!/usr/bin/env python3
"""Source IA — taux intérim (IFM, ICCP) (recherche web sourcée)."""
import sys
from pathlib import Path

_SCRAPING = Path(__file__).resolve().parent.parent
if str(_SCRAPING) not in sys.path:
    sys.path.insert(0, str(_SCRAPING))

from core.ai_scalar_source import run_ai_scalar_source  # noqa: E402

SCHEMA = {
    "type": "object",
    "properties": {
        "ifm_taux": {"type": ["number", "null"]},
        "indemnite_conges_taux": {"type": ["number", "null"]},
    },
    "required": ["ifm_taux", "indemnite_conges_taux"],
    "additionalProperties": False,
}

if __name__ == "__main__":
    run_ai_scalar_source(
        source_id="interim",
        libelle="Taux intérim (IFM, ICCP)",
        schema=SCHEMA,
        schema_name="interim",
        keys=["ifm_taux", "indemnite_conges_taux"],
        generator="interim/interim_AI.py",
        task_prompt=(
            "Intérim (travail temporaire) en France : "
            "1) taux de l'indemnité de fin de mission (IFM), FRACTION "
            "(ex : 0.10). "
            "2) taux de l'indemnité compensatrice de congés payés, FRACTION. "
            "Sources officielles (service-public, Code du travail L1251-32)."
        ),
        label="Intérim — IFM et ICCP (IA web)",
    )
