#!/usr/bin/env python3
"""Source IA — FNAL (recherche web)."""

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
        "taux_moins_50": {
            "type": ["number", "null"],
            "description": "Taux FNAL entreprises < 50 salariés en %",
        },
        "taux_50_et_plus": {
            "type": ["number", "null"],
            "description": "Taux FNAL entreprises ≥ 50 salariés en %",
        },
    },
    "required": ["taux_moins_50", "taux_50_et_plus"],
    "additionalProperties": False,
}


def _to_rate(percent: float | None) -> float | None:
    if percent is None:
        return None
    x = float(percent)
    if 0 < x < 0.02:
        return round(x, 6)
    return round(x / 100.0, 6)


def main() -> None:
    cy = current_year()
    data = extract_with_web_search(
        task_prompt=(
            f"Extrais les taux patronaux du FNAL (Fonds National d'Aide au Logement) "
            f"en vigueur en {cy} pour le régime général : taux_moins_50 (< 50 salariés) "
            f"et taux_50_et_plus (≥ 50 salariés). Renvoie les valeurs en pourcentage "
            f"(ex: 0.10 pour 0,10 %)."
        ),
        json_schema=SCHEMA,
        schema_name="fnal",
        include_domains=OFFICIAL,
    )
    if not data or data.get("taux_moins_50") is None or data.get("taux_50_et_plus") is None:
        print("ERREUR CRITIQUE: extraction IA FNAL échouée.", file=sys.stderr)
        sys.exit(1)

    sections = {
        "salarial": None,
        "patronal_moins_50": _to_rate(data.get("taux_moins_50")),
        "patronal_50_et_plus": _to_rate(data.get("taux_50_et_plus")),
    }
    payload = build_standard_payload(
        item_id="fnal",
        item_type="cotisation",
        libelle="Fonds National d'Aide au Logement (FNAL)",
        sections_or_valeurs=sections,
        generator="FNAL/FNAL_AI.py",
        source_url=URL,
        source_label="URSSAF FNAL (IA web)",
    )
    emit_ai_payload_or_exit(payload, "fnal")


if __name__ == "__main__":
    main()
