#!/usr/bin/env python3
"""Source IA — MMID patronal maladie (recherche web)."""

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
        "taux_plein_percent": {
            "type": ["number", "null"],
            "description": "Taux patronal plein MMID en %",
        },
        "taux_reduit_percent": {
            "type": ["number", "null"],
            "description": "Taux patronal réduit MMID en %",
        },
    },
    "required": ["taux_plein_percent", "taux_reduit_percent"],
    "additionalProperties": False,
}


def main() -> None:
    cy = current_year()
    data = extract_with_web_search(
        task_prompt=(
            f"Extrais les taux patronaux de la cotisation maladie MMID "
            f"(Assurance Maladie, Maternité, Invalidité, Décès) applicables en {cy} : "
            f"taux plein (droit commun) et taux réduit (bas salaires). "
            f"Renvoie taux_plein_percent et taux_reduit_percent en pourcentage."
        ),
        json_schema=SCHEMA,
        schema_name="mmid_patronal",
        include_domains=OFFICIAL,
    )
    if not data or data.get("taux_plein_percent") is None or data.get("taux_reduit_percent") is None:
        print("ERREUR CRITIQUE: extraction IA MMID patronal échouée.", file=sys.stderr)
        sys.exit(1)

    payload = build_standard_payload(
        item_id="securite_sociale_maladie",
        item_type="cotisation",
        libelle="Sécurité sociale - Maladie, Maternité, Invalidité, Décès",
        sections_or_valeurs={
            "salarial": None,
            "patronal_plein": round(float(data["taux_plein_percent"]) / 100.0, 6),
            "patronal_reduit": round(float(data["taux_reduit_percent"]) / 100.0, 6),
        },
        generator="MMIDpatronal/MMIDpatronal_AI.py",
        source_url=URL,
        source_label="URSSAF MMID patronal (IA web)",
        use_valeurs=True,
    )
    payload["base"] = "brut"
    emit_ai_payload_or_exit(payload, "securite_sociale_maladie")


if __name__ == "__main__":
    main()
