# scripts/CSA/CSA_AI.py

#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
CSA_AI.py
Recherche le taux patronal de la Contribution Solidarité Autonomie (CSA)
sur le web via DDGS, analyse les pages avec 'requests' et 'BeautifulSoup',
et utilise l'IA (GPT) pour extraire le taux officiel applicable.
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

SEARCH_QUERY_TEMPLATE = "taux contribution solidarité autonomie CSA URSSAF site:urssaf.fr OR site:legisocial.fr {year}"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36"
)


# --- UTILITAIRES ---


def iso_now() -> str:
    """Retourne la date et l'heure actuelles au format ISO 8601 UTC."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _fetch_text_with_requests(url: str) -> str | None:
    """Récupère le texte brut d'une page web via requests et BeautifulSoup."""
    try:
        r = requests.get(url, timeout=15, headers={"User-Agent": USER_AGENT})
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        return soup.get_text(" ", strip=True)
    except Exception as e:
        print(f"ERREUR (CSA_AI): Échec fetch Requests sur {url}: {e}", file=sys.stderr)
        return None


def _extract_rate_with_gpt(page_text: str) -> float | None:
    """Extrait le taux patronal de la CSA via GPT."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("ERREUR (CSA_AI): Clé OPENAI_API_KEY manquante.", file=sys.stderr)
        return None

    client = OpenAI(api_key=api_key)
    current_year = datetime.now().year

    prompt = (
        f"Analyse ce texte pour extraire le taux patronal de la 'Contribution Solidarité Autonomie (CSA)' "
        f"applicable en France pour l'année {current_year}.\n"
        "- Ignore les valeurs historiques.\n"
        "Retourne un JSON strict au format :\n"
        "{\n"
        '  "csa_percent": <float|null>\n'
        "}\n"
        "- La valeur doit être en pourcentage (ex: 0.30 pour 0,30%).\n"
        "- Si aucune valeur trouvée, mets null.\n"
        "- Ne renvoie que du JSON pur.\n\n"
        "Texte à analyser (max 15000 caractères):\n---\n" + page_text[:15000]
    )

    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            response_format={"type": "json_object"},
            temperature=0,
            messages=[
                {
                    "role": "system",
                    "content": "Assistant d'extraction JSON pur pour taux CSA.",
                },
                {"role": "user", "content": prompt},
            ],
        )
        data = json.loads(resp.choices[0].message.content.strip())
        val = data.get("csa_percent")
        if val is None:
            return None
        try:
            return round(float(str(val).replace(",", ".")) / 100.0, 6)
        except Exception:
            return None
    except Exception as e:
        print(f"ERREUR (CSA_AI): Extraction IA échouée: {e}", file=sys.stderr)
        return None


def build_payload(rate_patronal: float | None, found_url: str | None) -> dict:
    """Construit la charge utile JSON finale."""
    source_url = (
        found_url
        or "https://www.urssaf.fr/accueil/outils-documentation/taux-baremes/taux-cotisations-secteur-prive.html"
    )
    source_label = "URSSAF — Taux secteur privé"

    return {
        "id": "csa",
        "type": "cotisation",
        "libelle": "Contribution Solidarité Autonomie (CSA)",
        "base": "brut",
        "valeurs": {
            "salarial": None,
            "patronal": rate_patronal,
        },
        "meta": {
            "source": [{"url": source_url, "label": source_label, "date_doc": ""}],
            "scraped_at": iso_now(),
            "generator": "CSA/CSA.py",
            "method": "primary",
        },
    }


# --- FONCTION PRINCIPALE ---


def main() -> None:
    current_year = datetime.now().year
    SEARCH_QUERY = SEARCH_QUERY_TEMPLATE.format(year=current_year)
    print(
        f"INFO (CSA_AI): Démarrage. Recherche DDGS: '{SEARCH_QUERY}'", file=sys.stderr
    )

    results = []
    try:
        search_results = DDGS().text(SEARCH_QUERY, region="fr-fr", max_results=10)
        if search_results:
            results = [r["href"] for r in search_results]
        if not results:
            print("ERREUR (CSA_AI): DDGS n'a retourné aucun résultat.", file=sys.stderr)
    except Exception as e:
        print(f"ERREUR (CSA_AI): Échec de la recherche DDGS: {e}", file=sys.stderr)

    rate = None
    successful_url = None

    for url in results:
        print(f"INFO (CSA_AI): Analyse URL: {url}", file=sys.stderr)
        txt = _fetch_text_with_requests(url)
        if not txt:
            print("INFO (CSA_AI): ...Échec fetch ou texte vide.", file=sys.stderr)
            continue

        rate = _extract_rate_with_gpt(txt)
        if rate is not None:
            print(f"INFO (CSA_AI): Taux trouvé sur cette URL: {rate}", file=sys.stderr)
            successful_url = url
            break
        else:
            print("INFO (CSA_AI): ...Taux non trouvé sur cette URL.", file=sys.stderr)

    if rate is None:
        print("ERREUR (CSA_AI): Aucun taux trouvé après analyse.", file=sys.stderr)

    payload = build_payload(rate, successful_url)
    print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
