#!/usr/bin/env python3
"""Source IA — MMID salarial Alsace-Moselle (recherche web)."""

import sys
from pathlib import Path

_SCRAPING = Path(__file__).resolve().parent.parent
if str(_SCRAPING) not in sys.path:
    sys.path.insert(0, str(_SCRAPING))

from core.ai_extractor import build_standard_payload, emit_ai_payload_or_exit, extract_with_web_search  # noqa: E402
from core.year_utils import current_year  # noqa: E402

URL = "https://www.urssaf.fr/accueil/outils-documentation/taux-baremes/taux-cotisations-secteur-prive.html"

SCHEMA = {
    "type": "object",
    "properties": {"taux_salarial_percent": {"type": ["number", "null"]}},
    "required": ["taux_salarial_percent"],
    "additionalProperties": False,
}


def main() -> None:
    data = extract_with_web_search(
        task_prompt=(
            f"Extrais le taux SALARIAL de la cotisation maladie supplémentaire "
            f"Alsace-Moselle (régime local) applicable en {current_year()} (en %)."
        ),
        json_schema=SCHEMA,
        schema_name="mmid_alsace",
        include_domains=["urssaf.fr", "legisocial.fr"],
    )
    if not data or data.get("taux_salarial_percent") is None:
        print("ERREUR CRITIQUE: extraction IA MMID salarial échouée.", file=sys.stderr)
        sys.exit(1)

    rate = round(float(data["taux_salarial_percent"]) / 100.0, 6)
    payload = build_standard_payload(
        item_id="securite_sociale_maladie",
        item_type="cotisation",
        libelle="Maladie Alsace-Moselle salarial",
        sections_or_valeurs={
            "alsace_moselle": {"taux_salarial": rate},
        },
        generator="MMIDsalarial/MMIDsalarial_AI.py",
        source_url=URL,
        source_label="URSSAF MMID Alsace (IA web)",
    )
    emit_ai_payload_or_exit(payload, "securite_sociale_maladie")


if __name__ == "__main__":
    main()
