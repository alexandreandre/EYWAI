#!/usr/bin/env python3
"""Source IA — allocations familiales (recherche web)."""

import json
import sys
from pathlib import Path

_SCRAPING = Path(__file__).resolve().parent.parent
if str(_SCRAPING) not in sys.path:
    sys.path.insert(0, str(_SCRAPING))

from core.ai_extractor import build_standard_payload, emit_ai_payload_or_exit, extract_with_web_search  # noqa: E402
from core.year_utils import current_year  # noqa: E402

URL = (
    "https://www.urssaf.fr/accueil/employeur/cotisations/liste-cotisations/"
    "allocations-familiales.html"
)

OFFICIAL = [
    "urssaf.fr",
    "service-public.fr",
    "legifrance.gouv.fr",
    "agirc-arrco.fr",
    "bofip.impots.gouv.fr",
]

SCHEMA = {
    "type": "object",
    "properties": {
        "plein": {
            "type": ["number", "null"],
            "description": "Taux patronal plein (droit commun) en %",
        },
        "reduit": {
            "type": ["number", "null"],
            "description": "Taux patronal réduit (≤ 3,5 SMIC) en %",
        },
    },
    "required": ["plein", "reduit"],
    "additionalProperties": False,
}


def main() -> None:
    cy = current_year()
    data = extract_with_web_search(
        task_prompt=(
            f"Extrais les deux taux patronaux des allocations familiales URSSAF "
            f"applicables en {cy} : taux plein (droit commun) et taux réduit "
            f"(rémunérations ≤ 3,5 SMIC). Renvoie plein et reduit en pourcentage."
        ),
        json_schema=SCHEMA,
        schema_name="allocations_familiales",
        include_domains=OFFICIAL,
    )
    if not data or data.get("plein") is None or data.get("reduit") is None:
        print("ERREUR CRITIQUE: extraction IA allocations familiales échouée.", file=sys.stderr)
        sys.exit(1)

    payload = build_standard_payload(
        item_id="allocations_familiales",
        item_type="cotisation",
        libelle="Allocations familiales",
        sections_or_valeurs={
            "salarial": None,
            "patronal_plein": round(float(data["plein"]) / 100.0, 6),
            "patronal_reduit": round(float(data["reduit"]) / 100.0, 6),
        },
        generator="alloc/alloc_AI.py",
        source_url=URL,
        source_label="URSSAF allocations familiales (IA web)",
        use_valeurs=True,
    )
    payload["base"] = "brut"
    emit_ai_payload_or_exit(payload, "allocations_familiales")


if __name__ == "__main__":
    main()
