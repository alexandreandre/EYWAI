# scripts/SMIC/SMIC_AI.py

#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
SMIC_AI.py
Recherche le montant du SMIC horaire brut 2025 via le web, extrait le texte
et interroge GPT pour obtenir les trois montants (cas général, jeunes 17 ans, moins de 17 ans).
Produit un JSON strictement conforme au format attendu.
"""

import json
import os
import sys
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from ddgs.ddgs import DDGS
from openai import OpenAI

# --- CONFIGURATION ---
load_dotenv()
SEARCH_QUERY = "montant smic horaire brut URSSAF {year}"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36"
)


# --- UTILITAIRES ---
def iso_now() -> str:
    """Retourne la date et l'heure actuelles au format ISO 8601 UTC."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def extract_json_with_gpt(page_text: str) -> dict | None:
    """Interroge GPT-4o-mini pour extraire les trois montants du SMIC horaire."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("ERREUR : Variable OPENAI_API_KEY manquante.", file=sys.stderr)
        return None

    client = OpenAI(api_key=api_key)
    current_year = datetime.now().year
    today = datetime.now().strftime("%d/%m/%Y")

    prompt = f"""
Aujourd'hui, nous sommes le {today}.
Tu es un assistant expert en réglementation sociale française (URSSAF).
Extrait les montants du SMIC horaire brut pour {current_year}, pour :
1. Le cas général.
2. Les salariés entre 17 et 18 ans.
3. Les salariés de moins de 17 ans.

Format JSON strict attendu :
{{"cas_general":11.88,"entre_17_et_18_ans":10.69,"moins_de_17_ans":9.50}}

- Toutes les valeurs doivent être des nombres (float).
- Pas d'explication, pas de texte additionnel.
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
                {
                    "role": "system",
                    "content": "Assistant d'extraction. Ne renvoie que du JSON valide.",
                },
                {"role": "user", "content": prompt},
            ],
        )
        raw = resp.choices[0].message.content.strip()
        return json.loads(raw)
    except Exception as e:
        print(f"ERREUR extraction IA : {e}", file=sys.stderr)
        return None


# --- SCRAPER IA ---
def get_smic_via_ai() -> dict | None:
    """Recherche et extraction IA des montants du SMIC horaire."""
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
        print("ERREUR : Aucun résultat trouvé.", file=sys.stderr)
        return None

    for url in candidates:
        print(f"\n--- Tentative sur : {url} ---", file=sys.stderr)
        try:
            r = requests.get(url, timeout=20, headers={"User-Agent": USER_AGENT})
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")
            text = soup.get_text(" ", strip=True)

            data = extract_json_with_gpt(text)
            expected = {"cas_general", "entre_17_et_18_ans", "moins_de_17_ans"}

            if data and expected.issubset(data.keys()):
                print("✅ Extraction réussie.", file=sys.stderr)
                return data
            print("   - Données incomplètes, essai suivant.", file=sys.stderr)

        except Exception as e:
            print(f"   - ERREUR page : {e}", file=sys.stderr)

    print("\n❌ Aucune donnée valide extraite.", file=sys.stderr)
    return None


# --- MAIN ---
def main():
    """Orchestre l'extraction IA et génère le JSON final."""
    data = get_smic_via_ai()
    if not data:
        print("ERREUR CRITIQUE : Extraction échouée.", file=sys.stderr)
        sys.exit(1)

    smic_data = {
        "cas_general": data.get("cas_general"),
        "jeune_17_ans": data.get("entre_17_et_18_ans"),
        "jeune_moins_17_ans": data.get("moins_de_17_ans"),
    }

    payload = {
        "id": "smic_horaire",
        "type": "bareme_horaire",
        "libelle": "Salaire Minimum Interprofessionnel de Croissance (SMIC) - Taux horaire",
        "sections": smic_data,
        "meta": {
            "source": [
                {
                    "url": "https://www.urssaf.fr/accueil/outils-documentation/taux-baremes/montant-smic.html",
                    "label": "URSSAF - Montant du Smic",
                    "date_doc": "",
                }
            ],
            "scraped_at": iso_now(),
            "generator": "scripts/SMIC/SMIC_AI.py",
            "method": "ai",
        },
    }

    print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
