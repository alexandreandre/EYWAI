# scripts/PSS/PSS_AI.py

#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
PSS_AI.py
Recherche et extrait via l'IA les plafonds de la Sécurité Sociale (URSSAF) pour l'année courante.
Utilise DDGS pour trouver les pages pertinentes, BeautifulSoup pour extraire le texte,
et GPT pour obtenir les plafonds officiels. Format JSON final strictement conforme.
"""

import json
import os
import sys
import time
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from ddgs.ddgs import DDGS
from openai import OpenAI

# --- CONFIGURATION ---
load_dotenv()
SEARCH_QUERY = "plafonds sécurité sociale URSSAF {year}"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36"
)

# --- UTILITAIRES ---

def iso_now() -> str:
    """Retourne la date et l'heure actuelles au format ISO 8601 UTC."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def extract_json_with_gpt(page_text: str) -> dict | None:
    """Interroge GPT pour extraire les plafonds de la Sécurité Sociale."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("ERREUR : OPENAI_API_KEY manquant.", file=sys.stderr)
        return None

    client = OpenAI(api_key=api_key)
    current_year = datetime.now().year
    today = datetime.now().strftime("%d/%m/%Y")

    prompt = f"""
Aujourd'hui, nous sommes le {today}.
Tu es un assistant expert URSSAF. Extrait du texte suivant le barème complet des plafonds de la Sécurité Sociale applicables en {current_year}.
Je veux toutes les périodicités : Année, Trimestre, Mois, Quinzaine, Semaine, Jour, Heure.

Format strict attendu :
{{"annuel":47100,"trimestriel":11775,"mensuel":3925,"quinzaine":1963,"hebdomadaire":906,"journalier":216,"horaire":29}}

- Toutes les valeurs doivent être des entiers.
- Ne fournis que du JSON valide, sans texte additionnel.
Texte :
---
{page_text[:15000]}
---
""".strip()

    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            response_format={"type": "json_object"},
            temperature=0,
            messages=[
                {"role": "system", "content": "Assistant d'extraction JSON strict pour les barèmes URSSAF."},
                {"role": "user", "content": prompt},
            ],
        )
        raw = resp.choices[0].message.content.strip()
        return json.loads(raw)
    except Exception as e:
        print(f"ERREUR extraction IA : {e}", file=sys.stderr)
        return None


# --- SCRAPER IA ---

def get_plafonds_ss_via_ai() -> dict | None:
    """Recherche et extraction IA des plafonds de la Sécurité Sociale."""
    current_year = datetime.now().year
    query = SEARCH_QUERY.format(year=current_year)
    candidates = []

    try:
        print(f"Recherche DDGS : '{query}'", file=sys.stderr)
        for r in DDGS().text(query, region="fr-fr", max_results=5):
            url = r.get("href")
            if url and url not in candidates:
                candidates.append(url)

    except Exception as e:
        print(f"ERREUR recherche DDGS : {e}", file=sys.stderr)

    if not candidates:
        print("ERREUR : Aucun résultat valide trouvé.", file=sys.stderr)
        return None

    for url in candidates:
        print(f"\n--- Tentative sur : {url} ---", file=sys.stderr)
        try:
            r = requests.get(url, timeout=20, headers={"User-Agent": USER_AGENT})
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")
            text = soup.get_text(" ", strip=True)

            data = extract_json_with_gpt(text)
            expected_keys = {"annuel", "trimestriel", "mensuel", "quinzaine", "hebdomadaire", "journalier", "horaire"}

            if data and expected_keys.issubset(data.keys()):
                print("✅ Extraction réussie et complète.", file=sys.stderr)
                return data
            print("   - Données incomplètes, essai suivant.", file=sys.stderr)

        except Exception as e:
            print(f"   - ERREUR lors du traitement de {url}: {e}", file=sys.stderr)
            time.sleep(1)

    print("\n❌ Aucune donnée valide extraite après toutes les tentatives.", file=sys.stderr)
    return None


# --- MAIN ---

def main():
    """Orchestre l'extraction et produit la sortie JSON finale."""
    plafonds = get_plafonds_ss_via_ai()
    if not plafonds:
        print("ERREUR CRITIQUE : Extraction échouée.", file=sys.stderr)
        sys.exit(1)

    payload = {
        "id": "plafonds_securite_sociale",
        "type": "bareme_plafond",
        "libelle": "Plafonds de la Sécurité Sociale",
        "sections": plafonds,
        "meta": {
            "source": [{
                "url": "https://www.urssaf.fr/accueil/outils-documentation/taux-baremes/plafonds-securite-sociale.html",
                "label": "URSSAF - Plafonds de la Sécurité Sociale",
                "date_doc": ""
            }],
            "scraped_at": iso_now(),
            "generator": "scripts/PSS/PSS_AI.py",
            "method": "ai"
        }
    }

    print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
