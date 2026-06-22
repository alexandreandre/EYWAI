#!/usr/bin/env python3
"""Source IA — contribution solidarité autonomie (recherche web)."""

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
        "csa_percent": {
            "type": ["number", "null"],
            "description": "Taux patronal CSA en % (ex: 0.30 pour 0,30 %)",
        }
    },
    "required": ["csa_percent"],
    "additionalProperties": False,
}


def main() -> None:
    cy = current_year()
    data = extract_with_web_search(
        task_prompt=(
            f"Extrais le taux patronal de la Contribution Solidarité Autonomie (CSA) "
            f"applicable en France pour {cy}. Renvoie csa_percent en pourcentage."
        ),
        json_schema=SCHEMA,
        schema_name="csa",
        include_domains=OFFICIAL,
    )
    if not data or data.get("csa_percent") is None:
        print("ERREUR CRITIQUE: extraction IA CSA échouée.", file=sys.stderr)
        sys.exit(1)

    rate = round(float(data["csa_percent"]) / 100.0, 6)
    payload = build_standard_payload(
        item_id="csa",
        item_type="cotisation",
        libelle="Contribution Solidarité Autonomie (CSA)",
        sections_or_valeurs={"salarial": None, "patronal": rate},
        generator="CSA/CSA_AI.py",
        source_url=URL,
        source_label="URSSAF CSA (IA web)",
        use_valeurs=True,
    )
    payload["base"] = "brut"
    emit_ai_payload_or_exit(payload, "csa")


if __name__ == "__main__":
    main()
