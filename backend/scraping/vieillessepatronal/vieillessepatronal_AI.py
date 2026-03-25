# scripts/vieillessepatronal/vieillessepatronal_AI.py

#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
vieillessepatronal_AI.py
Recherche les taux de cotisation patronale vieillesse (plafonné et déplafonné)
sur le web via DDGS, analyse les pages avec 'requests' et 'BeautifulSoup',
et utilise l'IA (GPT) pour extraire les deux taux officiels.
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

# --- Configuration ---
load_dotenv()

SEARCH_QUERY_TEMPLATE = "taux cotisation assurance vieillesse patronale URSSAF {year}"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36"
)

# --- Fonctions utilitaires ---


def iso_now() -> str:
    """Retourne l'heure actuelle au format ISO UTC."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _fetch_text_with_requests(url: str) -> str | None:
    """Récupère le texte brut d'une page web via requests et BeautifulSoup."""
    try:
        r = requests.get(url, timeout=15, headers={"User-Agent": USER_AGENT})
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        return soup.get_text(" ", strip=True)
    except Exception as e:
        print(
            f"ERREUR (VIEILLESSE_AI): Échec fetch Requests sur {url}: {e}",
            file=sys.stderr,
        )
        return None


def _extract_rates_with_gpt(page_text: str) -> dict[str, float | None] | None:
    """Extrait les taux patronaux plafonné/déplafonné de la cotisation vieillesse via GPT."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("ERREUR (VIEILLESSE_AI): Clé OPENAI_API_KEY manquante.", file=sys.stderr)
        return None

    client = OpenAI(api_key=api_key)
    current_year = datetime.now().year
    today = datetime.now().strftime("%d/%m/%Y")

    prompt = (
        f"Aujourd'hui, nous sommes le {today}.\n"
        f"Analyse ce texte pour extraire les taux patronaux de la cotisation 'Assurance vieillesse' applicables en France pour l'année {current_year}.\n"
        "- Deux taux doivent être extraits :\n"
        '  1. "plafonné" (taux sur la part jusqu’au plafond de la Sécurité sociale)\n'
        '  2. "déplafonné" (taux sur la totalité du salaire)\n\n'
        "Retourne un JSON strict du format suivant :\n"
        '{"plafond":8.55,"deplafond":2.02}\n\n'
        "- Aucune explication hors JSON.\n"
        "Ne te fie qu’à des informations provenant de sources URSSAF ou gouvernementales.\n"
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
                    "content": "Assistant d'extraction JSON pur, spécialisé URSSAF.",
                },
                {"role": "user", "content": prompt},
            ],
        )
        data = json.loads(resp.choices[0].message.content.strip())

        plafond = data.get("plafond")
        deplafond = data.get("deplafond")

        def to_rate(v):
            if v is None:
                return None
            try:
                return round(float(str(v).replace(",", ".")) / 100.0, 5)
            except Exception:
                return None

        return {"plafonne": to_rate(plafond), "deplafonne": to_rate(deplafond)}

    except Exception as e:
        print(f"ERREUR (VIEILLESSE_AI): Extraction IA échouée: {e}", file=sys.stderr)
        return None


# --- Fonction principale ---


def main() -> None:
    """Orchestre la recherche IA et génère le JSON final."""
    current_year = datetime.now().year
    SEARCH_QUERY = SEARCH_QUERY_TEMPLATE.format(year=current_year)
    print(
        f"INFO (VIEILLESSE_AI): Démarrage. Recherche DDGS: '{SEARCH_QUERY}'",
        file=sys.stderr,
    )

    results = []
    try:
        search_results = DDGS().text(SEARCH_QUERY, region="fr-fr", max_results=5)
        if search_results:
            results = [r["href"] for r in search_results]
        if not results:
            print(
                "ERREUR (VIEILLESSE_AI): DDGS n'a retourné aucun résultat.",
                file=sys.stderr,
            )
    except Exception as e:
        print(
            f"ERREUR (VIEILLESSE_AI): Échec recherche DuckDuckGo: {e}", file=sys.stderr
        )

    rates = None
    successful_url = None

    for url in results:
        print(f"INFO (VIEILLESSE_AI): Analyse URL: {url}", file=sys.stderr)
        txt = _fetch_text_with_requests(url)
        if not txt:
            continue

        rates = _extract_rates_with_gpt(txt)
        if (
            rates
            and rates.get("plafonne") is not None
            and rates.get("deplafonne") is not None
        ):
            print(
                f"✅ Taux trouvés: plafonné={rates.get('plafonne')} déplafonné={rates.get('deplafonne')}",
                file=sys.stderr,
            )
            successful_url = url
            break
        else:
            print(
                "INFO (VIEILLESSE_AI): Données incomplètes, URL suivante.",
                file=sys.stderr,
            )
        time.sleep(1)

    if rates is None:
        print(
            "ERREUR (VIEILLESSE_AI): Aucun taux trouvé après analyse.", file=sys.stderr
        )

    payload = {
        "id": "assurance_vieillesse_patronal",
        "type": "taux_cotisation",
        "libelle": "Taux de cotisation patronale - Assurance Vieillesse",
        "sections": rates or {"deplafonne": None, "plafonne": None},
        "meta": {
            "source": [
                {
                    "url": successful_url or "N/A",
                    "label": "Source IA (via DDGS)"
                    if successful_url
                    else "N/A (Taux non trouvé par l'IA)",
                    "date_doc": "",
                }
            ],
            "scraped_at": iso_now(),
            "generator": "scripts/vieillessepatronal/vieillessepatronal_AI.py",
            "method": "ai",
        },
    }

    print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
