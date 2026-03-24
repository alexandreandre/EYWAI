# scripts/IJmaladie/IJmaladie_AI.py

#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
IJmaladie_AI.py
Recherche les montants maximums des indemnités journalières (IJ) sur le site ameli.fr,
puis extrait automatiquement les valeurs officielles via GPT à la date du jour.
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

load_dotenv()

SEARCH_QUERY_TEMPLATE = (
    "montants maximum indemnités journalières ameli {year} site:ameli.fr"
)
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36"
)


# --- UTILITAIRES ---

def iso_now() -> str:
    """Retourne la date et l'heure actuelles au format ISO 8601 UTC."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _fetch_text_with_requests(url: str) -> str | None:
    """Récupère le texte brut d'une page web via requests."""
    try:
        r = requests.get(url, timeout=15, headers={"User-Agent": USER_AGENT})
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        return soup.get_text(" ", strip=True)
    except Exception as e:
        print(f"ERREUR (IJMALADIE_AI): Échec fetch Requests sur {url}: {e}", file=sys.stderr)
        return None


def _extract_json_with_gpt(page_text: str) -> dict | None:
    """Extrait les 4 montants maximums des indemnités journalières à la date du jour."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("ERREUR (IJMALADIE_AI): Clé OPENAI_API_KEY manquante.", file=sys.stderr)
        return None

    client = OpenAI(api_key=api_key)
    current_year = datetime.now().year
    today_str = datetime.now().strftime("%A %d %B %Y")

    prompt = (
        f"Nous sommes le {today_str}. "
        f"Analyse attentivement le texte suivant et identifie les montants maximums en vigueur à cette date "
        f"des indemnités journalières de la Sécurité sociale (IJSS) en France pour l'année {current_year}.\n\n"
        "Tu dois extraire les quatre montants suivants :\n"
        '1. maladie\n'
        '2. maternite_paternite\n'
        '3. at_mp (accidents du travail / maladies professionnelles)\n'
        '4. at_mp_majoree (version majorée de l’AT/MP)\n\n'
        "Ignore toute mention d'années précédentes ou de valeurs périmées. Garde uniquement les chiffres actuels "
        "correspondant aux montants maximums en euros par jour.\n\n"
        "Retourne un JSON strict avec les clés suivantes et leurs valeurs numériques (pas de texte, pas de symbole €) :\n"
        "{\n"
        '  \"maladie\": <float|null>,\n'
        '  \"maternite_paternite\": <float|null>,\n'
        '  \"at_mp\": <float|null>,\n'
        '  \"at_mp_majoree\": <float|null>\n'
        "}\n"
        "- Si une valeur est absente, mets null.\n"
        "- Ne renvoie AUCUNE explication, uniquement du JSON pur.\n\n"
        "Texte à analyser (max 15000 caractères) :\n---\n"
        + page_text[:15000]
    )

    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            response_format={"type": "json_object"},
            temperature=0,
            messages=[
                {"role": "system", "content": "Assistant d'extraction JSON pur expert en Sécurité sociale française."},
                {"role": "user", "content": prompt},
            ],
        )
        data = json.loads(resp.choices[0].message.content.strip())
        return {
            "maladie": data.get("maladie"),
            "maternite_paternite": data.get("maternite_paternite"),
            "at_mp": data.get("at_mp"),
            "at_mp_majoree": data.get("at_mp_majoree"),
        }
    except Exception as e:
        print(f"ERREUR (IJMALADIE_AI): Extraction IA échouée: {e}", file=sys.stderr)
        return None


def build_payload(vals: dict | None, found_url: str | None) -> dict:
    """Construit le JSON final dans le format attendu."""
    valeurs = {
        "maladie": None,
        "maternite_paternite": None,
        "at_mp": None,
        "at_mp_majoree": None,
        "unite": "EUR/jour",
    }
    if vals:
        valeurs.update({
            "maladie": vals.get("maladie"),
            "maternite_paternite": vals.get("maternite_paternite"),
            "at_mp": vals.get("at_mp"),
            "at_mp_majoree": vals.get("at_mp_majoree"),
        })

    source_url = (
        found_url
        or "https://www.ameli.fr/entreprise/vos-salaries/montants-reference/indemnites-journalieres-montants-maximum"
    )
    source_label = "ameli.fr — IJ montants maximum"

    return {
        "id": "ij_maladie",
        "type": "secu",
        "libelle": "Indemnités journalières — montants maximums",
        "base": None,
        "valeurs": valeurs,
        "meta": {
            "source": [{"url": source_url, "label": source_label, "date_doc": ""}],
            "scraped_at": iso_now(),
            "generator": "scripts/IJmaladie/IJmaladie.py",
            "method": "primary",
        },
    }


def main() -> None:
    """Orchestre la recherche et l’extraction des montants IJSS via IA."""
    current_year = datetime.now().year
    SEARCH_QUERY = SEARCH_QUERY_TEMPLATE.format(year=current_year)
    print(f"INFO (IJMALADIE_AI): Démarrage. Recherche DDGS: '{SEARCH_QUERY}'", file=sys.stderr)

    results = []
    try:
        search_results = DDGS().text(SEARCH_QUERY, region="fr-fr", max_results=10)
        if search_results:
            results = [r["href"] for r in search_results]
        if not results:
            print("ERREUR (IJMALADIE_AI): DDGS n'a retourné aucun résultat.", file=sys.stderr)
    except Exception as e:
        print(f"ERREUR (IJMALADIE_AI): Échec de la recherche DDGS: {e}", file=sys.stderr)

    vals, successful_url = None, None
    for url in results:
        print(f"INFO (IJMALADIE_AI): Analyse URL: {url}", file=sys.stderr)
        txt = _fetch_text_with_requests(url)
        if not txt:
            print("INFO (IJMALADIE_AI): ...Échec fetch ou texte vide.", file=sys.stderr)
            continue

        data = _extract_json_with_gpt(txt)
        if data and all(k in data and data[k] is not None for k in ("maladie", "maternite_paternite", "at_mp", "at_mp_majoree")):
            vals = data
            successful_url = url
            print(f"INFO (IJMALADIE_AI): Données trouvées sur {url}", file=sys.stderr)
            break

    if vals is None:
        print("ERREUR (IJMALADIE_AI): Aucun montant trouvé après analyse.", file=sys.stderr)

    payload = build_payload(vals, successful_url)
    print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
