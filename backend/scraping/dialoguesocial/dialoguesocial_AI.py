# scripts/dialoguesocial/dialoguesocial_AI.py

#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
dialoguesocial_AI.py
Recherche le taux de la contribution au financement du dialogue social
sur le web via DDGS, analyse les pages avec 'requests' et 'BeautifulSoup',
et utilise l'IA (GPT) pour extraire la valeur officielle en vigueur à la date du jour.
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
    "taux contribution dialogue social URSSAF site:urssaf.fr OR site:legisocial.fr {year}"
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
    """Récupère le texte brut d'une page web via requests et BeautifulSoup."""
    try:
        r = requests.get(url, timeout=15, headers={"User-Agent": USER_AGENT})
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        return soup.get_text(" ", strip=True)
    except Exception as e:
        print(f"ERREUR (DIALOGUE_SOCIAL_AI): Échec fetch Requests sur {url}: {e}", file=sys.stderr)
        return None


def _extract_rate_with_gpt(page_text: str) -> dict | None:
    """Demande à GPT d'extraire le taux actuel de la contribution au dialogue social."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("ERREUR (DIALOGUE_SOCIAL_AI): Clé OPENAI_API_KEY manquante.", file=sys.stderr)
        return None

    client = OpenAI(api_key=api_key)
    current_year = datetime.now().year
    today_str = datetime.now().strftime("%A %d %B %Y")

    prompt = (
        f"Nous sommes le {today_str}. "
        f"Analyse attentivement le texte suivant et identifie le taux en vigueur à cette date "
        f"de la 'Contribution au financement du dialogue social' (souvent abrégée 'Contribution dialogue social').\n\n"
        "Cette contribution est une cotisation patronale très faible (autour de 0,016 %). "
        "Ne considère pas les valeurs historiques, ni les mentions d'années précédentes.\n\n"
        "Donne uniquement la valeur actuellement applicable au taux général des employeurs, pas les cas particuliers.\n\n"
        "Retourne un JSON strict au format suivant :\n"
        "{\n"
        '  \"taux\": <float|null>\n'
        "}\n"
        "- La valeur doit être exprimée en pourcentage (ex: 0.016 pour 0,016 %).\n"
        "- Si aucune donnée actuelle n'est trouvée, mets null.\n"
        "- Ne renvoie que du JSON pur, sans texte additionnel.\n\n"
        "Texte à analyser (max 15000 caractères) :\n---\n"
        + page_text[:15000]
    )

    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            response_format={"type": "json_object"},
            temperature=0,
            messages=[
                {
                    "role": "system",
                    "content": "Assistant d'extraction JSON pur, spécialisé en législation sociale française.",
                },
                {"role": "user", "content": prompt},
            ],
        )
        data = json.loads(resp.choices[0].message.content.strip())
        return {"taux": data.get("taux")}
    except Exception as e:
        print(f"ERREUR (DIALOGUE_SOCIAL_AI): Extraction IA échouée: {e}", file=sys.stderr)
        return None


def build_payload(rate_pct: float | None, found_url: str | None) -> dict:
    """Construit la charge utile JSON finale."""
    try:
        rate_decimal = round(float(str(rate_pct).replace(",", ".")) / 100.0, 6) if rate_pct is not None else None
    except Exception:
        rate_decimal = None

    source_url = (
        found_url
        or "https://www.urssaf.fr/accueil/outils-documentation/taux-baremes/taux-cotisations-secteur-prive.html"
    )
    source_label = "URSSAF - Taux de cotisations secteur privé"

    return {
        "id": "dialogue_social",
        "type": "cotisation",
        "libelle": "Contribution au dialogue social",
        "sections": {
            "salarial": None,
            "patronal": rate_decimal,
        },
        "meta": {
            "source": [{"url": source_url, "label": source_label, "date_doc": ""}],
            "scraped_at": iso_now(),
            "generator": "scripts/dialoguesocial/dialoguesocial.py",
            "method": "primary",
        },
    }


def main() -> None:
    """Orchestre la recherche et l'extraction du taux via IA."""
    current_year = datetime.now().year
    SEARCH_QUERY = SEARCH_QUERY_TEMPLATE.format(year=current_year)
    print(f"INFO (DIALOGUE_SOCIAL_AI): Démarrage. Recherche DDGS: '{SEARCH_QUERY}'", file=sys.stderr)

    results = []
    try:
        search_results = DDGS().text(SEARCH_QUERY, region="fr-fr", max_results=10)
        if search_results:
            results = [r["href"] for r in search_results]
        if not results:
            print("ERREUR (DIALOGUE_SOCIAL_AI): DDGS n'a retourné aucun résultat.", file=sys.stderr)
    except Exception as e:
        print(f"ERREUR (DIALOGUE_SOCIAL_AI): Échec de la recherche DDGS: {e}", file=sys.stderr)

    rate, successful_url = None, None

    for url in results:
        print(f"INFO (DIALOGUE_SOCIAL_AI): Analyse URL: {url}", file=sys.stderr)
        txt = _fetch_text_with_requests(url)
        if not txt:
            print("INFO (DIALOGUE_SOCIAL_AI): ...Échec fetch ou texte vide.", file=sys.stderr)
            continue

        data = _extract_rate_with_gpt(txt)
        if data and data.get("taux") is not None:
            rate = data.get("taux")
            successful_url = url
            print(f"INFO (DIALOGUE_SOCIAL_AI): Taux trouvé sur {url}: {rate}", file=sys.stderr)
            break

    if rate is None:
        print("ERREUR (DIALOGUE_SOCIAL_AI): Aucun taux trouvé après analyse.", file=sys.stderr)

    payload = build_payload(rate, successful_url)
    print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
