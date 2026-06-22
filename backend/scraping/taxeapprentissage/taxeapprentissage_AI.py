#!/usr/bin/env python3
"""Source IA — taxe d'apprentissage (recherche web)."""

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

ZONE_SCHEMA = {
    "type": "object",
    "properties": {
        "taux_metropole": {"type": ["number", "null"]},
        "taux_alsace_moselle": {"type": ["number", "null"]},
    },
    "required": ["taux_metropole", "taux_alsace_moselle"],
    "additionalProperties": False,
}

SCHEMA = {
    "type": "object",
    "properties": {
        "part_principale": ZONE_SCHEMA,
        "solde": ZONE_SCHEMA,
    },
    "required": ["part_principale", "solde"],
    "additionalProperties": False,
}


def _zone_to_rates(zone: dict) -> dict:
    def _one(v):
        if v is None:
            return None
        return round(float(v) / 100.0, 6)

    return {
        "taux_metropole": _one(zone.get("taux_metropole")),
        "taux_alsace_moselle": _one(zone.get("taux_alsace_moselle")),
    }


def main() -> None:
    cy = current_year()
    data = extract_with_web_search(
        task_prompt=(
            f"Extrais les taux de la taxe d'apprentissage applicables en {cy} : "
            f"part_principale et solde, chacune avec taux_metropole et taux_alsace_moselle. "
            f"Renvoie les valeurs en pourcentage (0 si absent pour Alsace-Moselle solde)."
        ),
        json_schema=SCHEMA,
        schema_name="taxe_apprentissage",
        include_domains=OFFICIAL,
    )
    if not data or not data.get("part_principale") or not data.get("solde"):
        print("ERREUR CRITIQUE: extraction IA taxe apprentissage échouée.", file=sys.stderr)
        sys.exit(1)

    part_principale = _zone_to_rates(data["part_principale"])
    solde = _zone_to_rates(data["solde"])
    if part_principale["taux_metropole"] is None or solde["taux_metropole"] is None:
        print("ERREUR CRITIQUE: taux taxe apprentissage incomplets.", file=sys.stderr)
        sys.exit(1)

    total = {
        "taux_metropole": round(
            (part_principale["taux_metropole"] or 0) + (solde["taux_metropole"] or 0), 6
        ),
        "taux_alsace_moselle": round(
            (part_principale["taux_alsace_moselle"] or 0)
            + (solde["taux_alsace_moselle"] or 0),
            6,
        ),
    }
    sections = {
        "salarial": None,
        "part_principale": part_principale,
        "solde": solde,
        "total": total,
    }
    payload = build_standard_payload(
        item_id="taxe_apprentissage",
        item_type="cotisation",
        libelle="Taxe d'Apprentissage",
        sections_or_valeurs=sections,
        generator="taxeapprentissage/taxeapprentissage_AI.py",
        source_url=URL,
        source_label="URSSAF taxe apprentissage (IA web)",
    )
    emit_ai_payload_or_exit(payload, "taxe_apprentissage")


if __name__ == "__main__":
    main()
