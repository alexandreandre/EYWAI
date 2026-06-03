#!/usr/bin/env python3
"""Source IA — cotisation AGS (recherche web)."""

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
    "agirc-arrco.fr",
    "bofip.impots.gouv.fr",
]

SCHEMA = {
    "type": "object",
    "properties": {
        "taux_general": {
            "type": ["number", "null"],
            "description": "Taux patronal AGS général (hors ETT) en %",
        }
    },
    "required": ["taux_general"],
    "additionalProperties": False,
}


def main() -> None:
    cy = current_year()
    data = extract_with_web_search(
        task_prompt=(
            f"Extrais le taux patronal général de la cotisation AGS "
            f"(Assurance Garantie des Salaires) applicable en {cy}. "
            f"Ignore les taux pour les entreprises de travail temporaire (ETT). "
            f"Renvoie taux_general en pourcentage (ex: 0.25 pour 0,25 %)."
        ),
        json_schema=SCHEMA,
        schema_name="ags",
        include_domains=OFFICIAL,
    )
    if not data or data.get("taux_general") is None:
        print("ERREUR CRITIQUE: extraction IA AGS échouée.", file=sys.stderr)
        sys.exit(1)

    rate = round(float(data["taux_general"]) / 100.0, 6)
    payload = build_standard_payload(
        item_id="ags",
        item_type="cotisation",
        libelle="Cotisation AGS",
        sections_or_valeurs={"salarial": None, "patronal": rate},
        generator="AGS/AGS_AI.py",
        source_url=URL,
        source_label="URSSAF AGS (IA web)",
        use_valeurs=True,
    )
    payload["base"] = "brut"
    emit_ai_payload_or_exit(payload, "ags")


if __name__ == "__main__":
    main()
