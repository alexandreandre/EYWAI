#!/usr/bin/env python3
"""Source IA — contribution formation professionnelle (recherche web)."""

import sys
from pathlib import Path

_SCRAPING = Path(__file__).resolve().parent.parent
if str(_SCRAPING) not in sys.path:
    sys.path.insert(0, str(_SCRAPING))

from core.ai_extractor import build_standard_payload, emit_ai_payload_or_exit, extract_with_web_search  # noqa: E402
from core.year_utils import current_year  # noqa: E402

URL = (
    "https://www.urssaf.fr/accueil/employeur/cotisations/liste-cotisations/"
    "formation-professionnelle.html"
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
        "taux_moins_11": {
            "type": ["number", "null"],
            "description": "Taux CFP entreprises < 11 salariés en %",
        },
        "taux_11_et_plus": {
            "type": ["number", "null"],
            "description": "Taux CFP entreprises ≥ 11 salariés en %",
        },
    },
    "required": ["taux_moins_11", "taux_11_et_plus"],
    "additionalProperties": False,
}


def main() -> None:
    cy = current_year()
    data = extract_with_web_search(
        task_prompt=(
            f"Extrais les taux de la Contribution à la Formation Professionnelle (CFP) "
            f"applicables en {cy} : taux_moins_11 (< 11 salariés) et taux_11_et_plus "
            f"(≥ 11 salariés). Renvoie les valeurs en pourcentage."
        ),
        json_schema=SCHEMA,
        schema_name="cfp",
        include_domains=OFFICIAL,
    )
    if not data or data.get("taux_moins_11") is None or data.get("taux_11_et_plus") is None:
        print("ERREUR CRITIQUE: extraction IA CFP échouée.", file=sys.stderr)
        sys.exit(1)

    sections = {
        "salarial": None,
        "patronal_moins_11": round(float(data["taux_moins_11"]) / 100.0, 6),
        "patronal_11_et_plus": round(float(data["taux_11_et_plus"]) / 100.0, 6),
    }
    payload = build_standard_payload(
        item_id="cfp",
        item_type="cotisation",
        libelle="Contribution à la Formation Professionnelle (CFP)",
        sections_or_valeurs=sections,
        generator="CFP/CFP_AI.py",
        source_url=URL,
        source_label="URSSAF CFP (IA web)",
    )
    emit_ai_payload_or_exit(payload, "cfp")


if __name__ == "__main__":
    main()
