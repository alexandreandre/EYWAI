# scripts/assurancechomage/assurancechomage_AI.py

#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
assurancechomage_AI.py
Recherche le taux patronal de l’assurance chômage sur le web via DDGS,
analyse les pages avec 'requests' et 'BeautifulSoup',
et utilise l’IA (GPT) pour extraire le taux officiel applicable.
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

SEARCH_QUERY_TEMPLATE = "taux cotisation assurance chômage URSSAF {year}"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36"
)

# --- Fonctions utilitaires ---

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
        print(f"ERREUR (CHOMAGE_AI): Échec fetch Requests sur {url}: {e}", file=sys.stderr)
        return None

def _extract_rate_with_gpt(page_text: str) -> dict[str, float | None] | None:
    """Extrait le taux patronal de l’assurance chômage via GPT."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("ERREUR (CHOMAGE_AI): Clé OPENAI_API_KEY manquante.", file=sys.stderr)
        return None

    client = OpenAI(api_key=api_key)
    current_year = datetime.now().year

    prompt = (
        f"Analyse ce texte pour extraire le taux patronal de la cotisation d’assurance chômage applicable en France pour l’année {current_year}.\n"
        "- Il existe un seul taux général (employeur uniquement).\n"
        "- Ignore les taux spécifiques (CDD, intérim, intermittents, annexes, majorations, etc.).\n\n"
        "Retourne un JSON strict avec la clé suivante et sa valeur en pourcentage :\n"
        "{\n"
        '  "patronal": <float|null>\n'
        "}\n"
        "- Si la valeur est absente, mets null.\n"
        "- Ne renvoie que du JSON pur, sans texte additionnel.\n"
        "Ne te fie pas à n'importe quel site, ait du recul sur les résultats que tu donnes.\n"
        "- Le taux peut être exprimé sous diverses formes.\n\n"
        "Donne exactement la valeur à la date d'aujourd'hui"
        "Texte à analyser (max 15000 caractères):\n---\n"
        + page_text[:15000]
    )

    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            response_format={"type": "json_object"},
            temperature=0,
            messages=[
                {"role": "system", "content": "Assistant d'extraction JSON pur, focalisé sur le taux patronal de l’assurance chômage."},
                {"role": "user", "content": prompt},
            ],
        )
        data = json.loads(resp.choices[0].message.content.strip())
        val = data.get("patronal")

        def to_rate(v):
            if v is None:
                return None
            try:
                return round(float(str(v).replace(",", ".")) / 100.0, 6)
            except Exception:
                return None

        return {"patronal": to_rate(val)}

    except Exception as e:
        print(f"ERREUR (CHOMAGE_AI): Extraction IA échouée: {e}", file=sys.stderr)
        return None

def build_payload(rate: dict[str, float | None] | None, found_url: str | None) -> dict:
    """Construit le JSON final strict demandé."""
    source_url = found_url or "N/A"
    source_label = "Source IA (via DDGS)" if found_url else "N/A (Taux non trouvé par l'IA)"

    patronal = rate.get("patronal") if rate else None

    return {
        "id": "assurance_chomage",
        "type": "cotisation",
        "libelle": "Assurance Chômage",
        "base": "brut",
        "valeurs": {
            "salarial": None,
            "patronal": patronal,
        },
        "meta": {
            "source": [{"url": source_url, "label": source_label, "date_doc": ""}],
            "generator": "scripts/assurancechomage/assurancechomage_AI.py",
        },
    }

# --- Fonction principale ---

def main() -> None:
    current_year = datetime.now().year
    SEARCH_QUERY = SEARCH_QUERY_TEMPLATE.format(year=current_year)
    print(f"INFO (CHOMAGE_AI): Démarrage. Recherche DDGS: '{SEARCH_QUERY}'", file=sys.stderr)

    results = []
    try:
        search_results = DDGS().text(SEARCH_QUERY, region="fr-fr", max_results=10)
        if search_results:
            results = [r["href"] for r in search_results]
        if not results:
            print("ERREUR (CHOMAGE_AI): DDGS n'a retourné aucun résultat.", file=sys.stderr)
    except Exception as e:
        print(f"ERREUR (CHOMAGE_AI): Échec de la recherche DuckDuckGo: {e}", file=sys.stderr)

    rate = None
    successful_url = None

    for url in results:
        print(f"INFO (CHOMAGE_AI): Analyse URL: {url}", file=sys.stderr)
        txt = _fetch_text_with_requests(url)
        if not txt:
            print("INFO (CHOMAGE_AI): ...Échec fetch ou texte vide.", file=sys.stderr)
            continue

        rate = _extract_rate_with_gpt(txt)
        if rate and rate.get("patronal") is not None:
            print(f"INFO (CHOMAGE_AI): Taux trouvé sur cette URL: {rate.get('patronal')}", file=sys.stderr)
            successful_url = url
            break
        else:
            print("INFO (CHOMAGE_AI): ...Taux non trouvé sur cette URL.", file=sys.stderr)

    if rate is None:
        print("ERREUR (CHOMAGE_AI): Aucun taux trouvé après analyse.", file=sys.stderr)

    payload = build_payload(rate, successful_url)
    print(json.dumps(payload, ensure_ascii=False))

if __name__ == "__main__":
    main()
