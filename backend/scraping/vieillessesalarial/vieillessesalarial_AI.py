#!/usr/bin/env python3
"""Source IA — vieillesse salariale (recherche web)."""

import json
import sys
from pathlib import Path

_SCRAPING = Path(__file__).resolve().parent.parent
if str(_SCRAPING) not in sys.path:
    sys.path.insert(0, str(_SCRAPING))

from core.ai_extractor import build_standard_payload, emit_ai_payload_or_exit, extract_with_web_search  # noqa: E402
from core.year_utils import current_year  # noqa: E402

URL = "https://www.urssaf.fr/accueil/outils-documentation/taux-baremes/taux-cotisations-secteur-prive.html"

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
        "plafond_percent": {"type": ["number", "null"]},
        "deplafond_percent": {"type": ["number", "null"]},
    },
    "required": ["plafond_percent", "deplafond_percent"],
    "additionalProperties": False,
}


def main() -> None:
    cy = current_year()
    data = extract_with_web_search(
        task_prompt=(
            f"Extrais les deux taux SALARIAUX de l'assurance vieillesse URSSAF "
            f"applicables en {cy} : plafonné et déplafonné (en %). "
            f"Renvoie plafond_percent et deplafond_percent."
        ),
        json_schema=SCHEMA,
        schema_name="vieillesse_salarial",
        include_domains=OFFICIAL,
    )
    if not data or data.get("plafond_percent") is None or data.get("deplafond_percent") is None:
        print("ERREUR CRITIQUE: extraction IA vieillesse salariale échouée.", file=sys.stderr)
        sys.exit(1)

    sections = {
        "plafonne": round(float(data["plafond_percent"]) / 100.0, 6),
        "deplafonne": round(float(data["deplafond_percent"]) / 100.0, 6),
    }
    payload = build_standard_payload(
        item_id="vieillesse_salarial",
        item_type="cotisation",
        libelle="Assurance vieillesse salariale",
        sections_or_valeurs=sections,
        generator="vieillessesalarial/vieillessesalarial_AI.py",
        source_url=URL,
        source_label="URSSAF vieillesse salariale (IA web)",
    )
    emit_ai_payload_or_exit(payload, "vieillesse_salarial")


if __name__ == "__main__":
    main()
