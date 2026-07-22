#!/usr/bin/env python3
"""Source IA — régime alternance apprenti (seuils d'exonération, recherche web).

Valeur réglementaire prose (pas de tableau officiel scrappable de façon fiable) :
on s'appuie sur une extraction web sourcée (sonar-pro) avec citation officielle
obligatoire. Le garde-fou « tier critical » impose une revue humaine avant toute
écriture réelle : cette source MONITORE, elle n'écrase jamais la config seule.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

_SCRAPING = Path(__file__).resolve().parent.parent
if str(_SCRAPING) not in sys.path:
    sys.path.insert(0, str(_SCRAPING))

from core.ai_extractor import extract_with_web_search, last_citation  # noqa: E402
from openrouter_client import MODEL_WEB_SEARCH_PRO  # noqa: E402

OFFICIAL = [
    "boss.gouv.fr",
    "urssaf.fr",
    "service-public.fr",
    "legifrance.gouv.fr",
    "impots.gouv.fr",
]

SCHEMA = {
    "type": "object",
    "properties": {
        "apprenti_exo_pct_smic": {"type": ["number", "null"]},
        "apprenti_ir_plafond_pct_smic": {"type": ["number", "null"]},
    },
    "required": ["apprenti_exo_pct_smic", "apprenti_ir_plafond_pct_smic"],
    "additionalProperties": False,
}


def main() -> None:
    data = extract_with_web_search(
        task_prompt=(
            "Régime social et fiscal de l'APPRENTI en France (paie). "
            "1) Seuil actuellement EN VIGUEUR d'exonération de cotisations "
            "salariales de l'apprenti, exprimé en FRACTION du SMIC (le seuil a été "
            "abaissé au 01/03/2025). Donne la fraction (ex : 0.5 pour 50 %). "
            "2) Plafond d'exonération d'impôt sur le revenu du salaire de "
            "l'apprenti, en FRACTION du SMIC annuel (ex : 1.0 pour 100 %). "
            "Utilise uniquement des sources officielles récentes "
            "(BOSS, URSSAF, service-public, Légifrance, impots.gouv)."
        ),
        json_schema=SCHEMA,
        schema_name="apprenti_regime",
        include_domains=OFFICIAL,
        model=MODEL_WEB_SEARCH_PRO,
    )
    if not data or data.get("apprenti_exo_pct_smic") is None:
        print("ERREUR CRITIQUE: extraction IA alternance échouée.", file=sys.stderr)
        sys.exit(1)

    cit = last_citation()
    payload = {
        "id": "alternance",
        "type": "regime",
        "libelle": "Régime alternance — apprenti",
        "valeurs": {
            "apprenti_exo_pct_smic": data["apprenti_exo_pct_smic"],
            "apprenti_ir_plafond_pct_smic": data.get("apprenti_ir_plafond_pct_smic"),
        },
        "meta": {
            "source": [
                {
                    "url": cit.get("url", ""),
                    "label": "BOSS/URSSAF — apprenti (IA web)",
                    "date_doc": cit.get("date", ""),
                }
            ],
            "scraped_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "generator": "alternance/alternance_AI.py",
            "method": "ai_web_search",
        },
    }
    print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
