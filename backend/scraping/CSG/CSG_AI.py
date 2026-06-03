#!/usr/bin/env python3
"""Source IA — CSG/CRDS salariales (recherche web)."""

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
        "csg_imposable": {
            "type": ["number", "null"],
            "description": "CSG non déductible (imposable) en %",
        },
        "csg_non_imposable": {
            "type": ["number", "null"],
            "description": "CSG déductible en %",
        },
        "crds": {"type": ["number", "null"], "description": "CRDS en %"},
    },
    "required": ["csg_imposable", "csg_non_imposable", "crds"],
    "additionalProperties": False,
}


def main() -> None:
    cy = current_year()
    data = extract_with_web_search(
        task_prompt=(
            f"Extrais les taux salariaux CSG/CRDS du secteur privé en vigueur en {cy} : "
            f"csg_imposable (part non déductible), csg_non_imposable (part déductible) "
            f"et crds. Renvoie les valeurs en pourcentage."
        ),
        json_schema=SCHEMA,
        schema_name="csg_crds",
        include_domains=OFFICIAL,
    )
    if not data or any(data.get(k) is None for k in ("csg_imposable", "csg_non_imposable", "crds")):
        print("ERREUR CRITIQUE: extraction IA CSG/CRDS échouée.", file=sys.stderr)
        sys.exit(1)

    deductible = round(float(data["csg_non_imposable"]) / 100.0, 6)
    non_deductible = round(
        float(data["csg_imposable"]) / 100.0 + float(data["crds"]) / 100.0, 6
    )
    payload = build_standard_payload(
        item_id="csg",
        item_type="cotisation",
        libelle="CSG/CRDS",
        sections_or_valeurs={
            "salarial": {
                "deductible": deductible,
                "non_deductible": non_deductible,
            },
            "patronal": None,
        },
        generator="CSG/CSG_AI.py",
        source_url=URL,
        source_label="URSSAF CSG/CRDS (IA web)",
        use_valeurs=True,
    )
    payload["base"] = "brut"
    emit_ai_payload_or_exit(payload, "csg")


if __name__ == "__main__":
    main()
