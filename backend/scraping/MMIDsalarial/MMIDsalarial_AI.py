# scripts/MMIDsalarial/MMIDsalarial_AI.py

#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
MMIDsalarial_AI.py
Recherche le taux de cotisation salariale maladie supplémentaire (régime local Alsace-Moselle)
en interrogeant l’IA pour obtenir la valeur actuelle du jour.
"""

import json
import os
import sys
from datetime import datetime, timezone

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36"
)
SEARCH_QUERY = (
    "taux cotisation salariale maladie supplémentaire Alsace-Moselle URSSAF 2025 site:urssaf.fr"
)


# --- UTILITAIRES ---

def iso_now() -> str:
    """Retourne la date et l'heure actuelles au format ISO 8601 UTC."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _extract_taux_with_gpt() -> float | None:
    """Extrait le taux Alsace-Moselle actuel via GPT, à la date du jour."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("ERREUR (MMIDsalarial_AI): Clé OPENAI_API_KEY manquante.", file=sys.stderr)
        return None

    client = OpenAI(api_key=api_key)
    today_str = datetime.now().strftime("%A %d %B %Y")
    current_year = datetime.now().year

    prompt = (
        f"Nous sommes le {today_str}. "
        f"Quel est aujourd’hui le taux officiel de la 'cotisation salariale maladie' "
        f"applicable en Alsace-Moselle (régime local) en {current_year} selon l’URSSAF ?\n\n"
        "Indications :\n"
        "- Ce taux est uniquement SALARIAL (régime local Alsace-Moselle).\n"
        "- Il s’agit d’un petit pourcentage, autour d’environ 1,30 %.\n"
        "- Réponds uniquement en JSON strict : {\"taux_salarial\": <nombre|null>}.\n"
        "- La valeur doit être en pourcentage (ex: 1.30 pour 1,30 %).\n"
        "- Si tu ne trouves pas la valeur actuelle, mets null.\n"
        "- Ne renvoie que du JSON, sans texte additionnel.\n"
    )

    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": "Assistant d'extraction JSON spécialisé en cotisations sociales françaises."},
                {"role": "user", "content": prompt},
            ],
        )
        data = json.loads(resp.choices[0].message.content.strip())
        val = data.get("taux_salarial")

        if val is None:
            return None
        try:
            return round(float(str(val).replace(",", ".")) / 100.0, 5)
        except Exception:
            return None
    except Exception as e:
        print(f"ERREUR (MMIDsalarial_AI): Extraction IA échouée: {e}", file=sys.stderr)
        return None


def build_payload(rate: float | None) -> dict:
    """Construit le JSON final dans le format attendu."""
    source_url = "https://www.urssaf.fr/accueil/outils-documentation/taux-baremes/taux-cotisations-secteur-prive.html"
    source_label = "URSSAF - Taux de cotisations secteur privé"

    return {
        "id": "maladie_alsace_moselle",
        "type": "taux_cotisation_specifique",
        "libelle": "Taux de cotisation salariale maladie - Alsace-Moselle",
        "sections": {"alsace_moselle": {"taux_salarial": rate}},
        "meta": {
            "source": [{"url": source_url, "label": source_label, "date_doc": ""}],
            "scraped_at": iso_now(),
            "generator": "scripts/MMIDsalarial/MMIDsalarial.py",
            "method": "primary",
        },
    }


def main() -> None:
    """Orchestre l’extraction et construit le payload final."""
    rate = _extract_taux_with_gpt()
    if rate is None:
        print("ERREUR (MMIDsalarial_AI): Impossible d’extraire le taux actuel.", file=sys.stderr)
        sys.exit(1)

    payload = build_payload(rate)
    print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
