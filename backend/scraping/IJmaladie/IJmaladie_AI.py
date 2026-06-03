#!/usr/bin/env python3
"""Source IA IJSS — témoin Sonar (page Service Public A18779)."""

import sys
from pathlib import Path

_SCRAPING = Path(__file__).resolve().parent.parent
if str(_SCRAPING) not in sys.path:
    sys.path.insert(0, str(_SCRAPING))

from core.ai_extractor import (  # noqa: E402
    build_standard_payload,
    emit_ai_payload_or_exit,
    extract_with_web_search,
)
from core.year_utils import current_year  # noqa: E402

URL_SERVICE_PUBLIC = (
    "https://www.service-public.gouv.fr/particuliers/actualites/A18779"
)

SCHEMA = {
    "type": "object",
    "properties": {
        "maladie": {
            "type": ["number", "null"],
            "description": "Plafond journalier IJ maladie (€/jour)",
        },
        "maternite_paternite": {
            "type": ["number", "null"],
            "description": "Plafond journalier maternité/paternité/adoption (€/jour)",
        },
        "at_mp": {
            "type": ["number", "null"],
            "description": "Plafond AT/MP jusqu'au 28e jour (€/jour)",
        },
        "at_mp_majoree": {
            "type": ["number", "null"],
            "description": "Plafond AT/MP à compter du 29e jour (€/jour)",
        },
    },
    "required": ["maladie", "maternite_paternite", "at_mp", "at_mp_majoree"],
    "additionalProperties": False,
}


def main() -> None:
    cy = current_year()
    data = extract_with_web_search(
        task_prompt=(
            f"Extrais les montants maximums journaliers (€/jour) des indemnités "
            f"journalières de sécurité sociale (IJSS) en vigueur en {cy} depuis "
            f"la page Service Public {URL_SERVICE_PUBLIC} : "
            f"1) arrêt maladie, 2) maternité/paternité/adoption, "
            f"3) accident du travail / maladie professionnelle (jusqu'au 28e jour), "
            f"4) AT/MP majoré à compter du 29e jour. "
            f"Utilise cette URL comme citation_url."
        ),
        json_schema=SCHEMA,
        schema_name="ij_plafonds",
        include_domains=["service-public.gouv.fr", "legifrance.gouv.fr", "securite-sociale.fr"],
    )
    if not data or any(data.get(k) is None for k in SCHEMA["required"]):
        print("ERREUR CRITIQUE: extraction IA IJSS échouée.", file=sys.stderr)
        sys.exit(1)

    valeurs = {
        "maladie": round(float(data["maladie"]), 2),
        "maternite_paternite": round(float(data["maternite_paternite"]), 2),
        "at_mp": round(float(data["at_mp"]), 2),
        "at_mp_majoree": round(float(data["at_mp_majoree"]), 2),
        "unite": "EUR/jour",
    }

    payload = build_standard_payload(
        item_id="ij_maladie",
        item_type="secu",
        libelle="Indemnités journalières — montants maximums",
        sections_or_valeurs=valeurs,
        generator="IJmaladie/IJmaladie_AI.py",
        source_url=URL_SERVICE_PUBLIC,
        source_label="Service Public — IJSS montants (IA web)",
        use_valeurs=True,
    )
    emit_ai_payload_or_exit(payload, "ij_maladie")


if __name__ == "__main__":
    main()
