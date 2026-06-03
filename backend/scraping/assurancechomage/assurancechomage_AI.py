#!/usr/bin/env python3
"""Source IA — assurance chômage (recherche web)."""

import json
import sys
from pathlib import Path

_SCRAPING = Path(__file__).resolve().parent.parent
if str(_SCRAPING) not in sys.path:
    sys.path.insert(0, str(_SCRAPING))

from core.ai_extractor import build_standard_payload, emit_ai_payload_or_exit, extract_with_web_search  # noqa: E402
from core.year_utils import current_year  # noqa: E402

URL = (
    "https://www.urssaf.fr/accueil/outils-documentation/taux-baremes/"
    "taux-cotisations-secteur-prive.html"
)

OFFICIAL = [
    "urssaf.fr",
    "service-public.fr",
    "legifrance.gouv.fr",
    "unedic.org",
]

SCHEMA = {
    "type": "object",
    "properties": {
        "patronal_percent": {
            "type": ["number", "null"],
            "description": "Taux patronal assurance chômage en % (taux général uniquement)",
        }
    },
    "required": ["patronal_percent"],
    "additionalProperties": False,
}


def main() -> None:
    cy = current_year()
    data = extract_with_web_search(
        task_prompt=(
            f"Extrais le taux patronal général de la cotisation assurance chômage "
            f"applicable en France pour {cy} depuis {URL} ou unedic.org. "
            f"Taux général secteur privé uniquement (souvent 4 % en {cy}) — "
            f"ignore CDD intérim, intermittents et majorations. "
            f"Renvoie patronal_percent en pourcentage (ex. 4 pour 4 %)."
        ),
        json_schema=SCHEMA,
        schema_name="assurance_chomage",
        include_domains=OFFICIAL,
    )
    if not data or data.get("patronal_percent") is None:
        print("ERREUR CRITIQUE: extraction IA assurance chômage échouée.", file=sys.stderr)
        sys.exit(1)

    rate = round(float(data["patronal_percent"]) / 100.0, 6)
    payload = build_standard_payload(
        item_id="assurance_chomage",
        item_type="cotisation",
        libelle="Assurance Chômage",
        sections_or_valeurs={"salarial": None, "patronal": rate},
        generator="assurancechomage/assurancechomage_AI.py",
        source_url=URL,
        source_label="URSSAF assurance chômage (IA web)",
        use_valeurs=True,
    )
    payload["base"] = "brut"
    emit_ai_payload_or_exit(payload, "assurance_chomage")


if __name__ == "__main__":
    main()
