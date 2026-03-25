#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
AGS_AI.py
Recherche le taux de cotisation AGS sur le web (DDGS), analyse les
premiers résultats avec 'requests' et 'BeautifulSoup', et utilise
l'IA (GPT) pour extraire le taux général (hors ETT).
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

# --- Configuration ---
load_dotenv()

# L'année sera ajoutée dynamiquement
SEARCH_QUERY_TEMPLATE = "taux cotisation AGS URSSAF {year}"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36"
)

# --- Fonctions ---

def iso_now() -> str:
    """Retourne l'heure actuelle en format ISO UTC."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def _fetch_text_with_requests(url: str) -> str | None:
    """Récupère le texte brut d'une page web via requests/BeautifulSoup."""
    try:
        r = requests.get(url, timeout=15, headers={"User-Agent": USER_AGENT})
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        return soup.get_text(" ", strip=True)
    except Exception as e:
        print(f"ERREUR (AGS_AI): Échec fetch Requests sur {url}: {e}", file=sys.stderr)
        return None

def _extract_rate_with_gpt(page_text: str) -> float | None:
    """Extrait uniquement le taux AGS général via GPT."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("ERREUR (AGS_AI): Clé OPENAI_API_KEY manquante.", file=sys.stderr)
        return None

    client = OpenAI(api_key=api_key)
    current_year = datetime.now().year
    
    # Prompt conçu pour ignorer ETT et se concentrer sur le taux général
    prompt = (
        f"Extrait le pourcentage du taux patronal de la cotisation AGS (Assurance Garantie des Salaires) "
        f"en France pour l'année {current_year}. Ignore spécifiquement les taux pour les 'entreprises de travail temporaire' (ETT).\n"
        "- Réponds uniquement en JSON avec la clé: {{\"taux_general\": <nombre|null>}}\n"
        "- Ne garde que le taux général, pas le taux ETT.\n"
        "- Le taux doit être un nombre (ex: 0.25% -> 0.25). Pas de signe %, pas de texte.\n\n"
        "Texte à analyser (max 15000 chars):\n---\n"
        + page_text[:15000]
    )

    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            response_format={"type": "json_object"},
            temperature=0,
            messages=[
                {"role": "system", "content": "Assistant d'extraction JSON pur, focalisé sur le taux général."},
                {"role": "user", "content": prompt},
            ],
        )
        data = json.loads(resp.choices[0].message.content.strip())
        val = data.get("taux_general")
        
        if val is None:
            print("INFO (AGS_AI): L'IA n'a pas trouvé de 'taux_general'.", file=sys.stderr)
            return None
        
        # Conversion en taux (ex: 0.25 -> 0.0025)
        rate = round(float(str(val).replace(",", ".")) / 100.0, 6)
        return rate
        
    except Exception as e:
        print(f"ERREUR (AGS_AI): Extraction IA échouée: {e}", file=sys.stderr)
        return None

def build_payload(rate: float | None, found_url: str | None) -> dict:
    """Construit le JSON final strict demandé."""
    
    # Détermine la source
    if rate is not None and found_url:
        source_url = found_url
        source_label = "Source IA (via DDGS)"
    else:
        source_url = "N/A"
        source_label = "N/A (Taux non trouvé par l'IA)"
        
    return {
        "id": "ags",
        "type": "cotisation",
        "libelle": "Cotisation AGS",
        "base": "brut",
        "valeurs": {
            "salarial": None,
            "patronal": rate  # CORRIGÉ: renvoie 'null' si rate est None
        },
        "meta": {
            "source": [
                {
                    "url": source_url,
                    "label": source_label,
                    "date_doc": ""
                }
            ],
            "generator": "scripts/AGS/AGS_AI.py" # CORRIGÉ: nom du script
        },
    }

def main() -> None:
    current_year = datetime.now().year
    SEARCH_QUERY = SEARCH_QUERY_TEMPLATE.format(year=current_year)
    print(f"INFO (AGS_AI): Démarrage. Recherche DDGS: '{SEARCH_QUERY}'", file=sys.stderr)
    
    results = []
    try:
        # 1. Recherche DuckDuckGo
        search_results = DDGS().text(SEARCH_QUERY, region="fr-fr", max_results=5)
        if search_results:
            results = [r["href"] for r in search_results]
        if not results:
             print("ERREUR (AGS_AI): DDGS n'a retourné aucun résultat.", file=sys.stderr)
             
    except Exception as e:
        print(f"ERREUR (AGS_AI): Échec de la recherche DuckDuckGo: {e}", file=sys.stderr)

    rate = None
    successful_url = None

    # 2. Itération sur les 5 URL
    for url in results:
        print(f"INFO (AGS_AI): Analyse URL: {url}", file=sys.stderr)
        
        # 3. Fetch du texte (sans Selenium)
        txt = _fetch_text_with_requests(url)
        if not txt:
            print("INFO (AGS_AI): ...Échec fetch ou texte vide.", file=sys.stderr)
            continue
        
        # 4. Extraction IA
        rate = _extract_rate_with_gpt(txt)
        
        # 5. Si trouvé, on arrête
        if rate is not None:
            print(f"INFO (AGS_AI): Taux trouvé sur cette URL: {rate}", file=sys.stderr)
            successful_url = url
            break
        else:
             print("INFO (AGS_AI): ...Taux non trouvé par l'IA sur cette URL.", file=sys.stderr)

    if rate is None:
        print("ERREUR (AGS_AI): Taux non trouvé après analyse des URLs.", file=sys.stderr)

    # 6. Construit le payload (même s'il a échoué, pour renvoyer 'null')
    payload = build_payload(rate, successful_url)
    print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()