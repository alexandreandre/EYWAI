#!/usr/bin/env python3
"""Source IA — contribution dialogue social (recherche web)."""

import json
import sys
from pathlib import Path

_SCRAPING = Path(__file__).resolve().parent.parent
if str(_SCRAPING) not in sys.path:
    sys.path.insert(0, str(_SCRAPING))

from core.ai_extractor import build_standard_payload, emit_ai_payload_or_exit, extract_with_web_search  # noqa: E402

URL_URSSAF = (
    "https://www.urssaf.fr/accueil/outils-documentation/taux-baremes/"
    "taux-cotisations-secteur-prive.html"
)

SCHEMA = {
    "type": "object",
    "properties": {
        "patronal_percent": {
            "type": ["number", "null"],
            "description": "Taux patronal en pourcentage (ex 0.016 pour 0,016 %)",
        }
    },
    "required": ["patronal_percent"],
    "additionalProperties": False,
}


def main() -> None:
    data = extract_with_web_search(
        task_prompt=(
            "Extrais le taux patronal de la contribution au dialogue social "
            "(secteur privé, France). Renvoie patronal_percent en pourcentage "
            "(exemple: 0.016 pour 0,016 %)."
        ),
        json_schema=SCHEMA,
        schema_name="dialogue_social",
        include_domains=["urssaf.fr", "legisocial.fr"],
    )
    if not data or data.get("patronal_percent") is None:
        print("ERREUR CRITIQUE: extraction IA dialogue social échouée.", file=sys.stderr)
        sys.exit(1)

    rate = round(float(data["patronal_percent"]) / 100.0, 6)
    payload = build_standard_payload(
        item_id="dialogue_social",
        item_type="cotisation",
        libelle="Contribution au dialogue social",
        sections_or_valeurs={"salarial": None, "patronal": rate},
        generator="dialoguesocial/dialoguesocial_AI.py",
        source_url=URL_URSSAF,
        source_label="URSSAF — dialogue social (IA web)",
        use_valeurs=True,
    )
    payload["base"] = "brut"
    emit_ai_payload_or_exit(payload, "dialogue_social")


if __name__ == "__main__":
    main()
