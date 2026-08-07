#!/usr/bin/env python3
"""Source IA — taux CDD (prime de précarité, ICCP) (recherche web sourcée)."""
import sys
from pathlib import Path

_SCRAPING = Path(__file__).resolve().parent.parent
if str(_SCRAPING) not in sys.path:
    sys.path.insert(0, str(_SCRAPING))

from core.ai_scalar_source import run_ai_scalar_source  # noqa: E402

SCHEMA = {
    "type": "object",
    "properties": {
        "precarite_taux": {"type": ["number", "null"]},
        "indemnite_conges_taux": {"type": ["number", "null"]},
    },
    "required": ["precarite_taux", "indemnite_conges_taux"],
    "additionalProperties": False,
}

if __name__ == "__main__":
    run_ai_scalar_source(
        source_id="cdd",
        libelle="Taux CDD (précarité, ICCP)",
        schema=SCHEMA,
        schema_name="cdd",
        keys=["precarite_taux", "indemnite_conges_taux"],
        generator="cdd/cdd_AI.py",
        task_prompt=(
            "Contrat à durée déterminée (CDD) en France : "
            "1) taux de l'indemnité de fin de contrat (prime de précarité), "
            "en FRACTION (ex : 0.10 pour 10 %). "
            "2) taux de l'indemnité compensatrice de congés payés, "
            "en FRACTION (ex : 0.10). "
            "Sources officielles (service-public, Légifrance, Code du travail "
            "L1243-8)."
        ),
        label="CDD — prime de précarité et ICCP (IA web)",
    )
