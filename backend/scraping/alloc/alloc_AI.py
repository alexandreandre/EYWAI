# scripts/alloc/alloc_AI.py

#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
alloc_AI.py
Recherche les taux patronaux des allocations familiales (plein et réduit)
via DDGS, analyse les pages avec 'requests' et 'BeautifulSoup',
et utilise l'IA (GPT) pour extraire les deux taux officiels URSSAF.
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

SEARCH_QUERY_TEMPLATE = "site:urssaf.fr taux cotisation allocations familiales employeur {year} taux plein et réduit"
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
        r = requests.get(url, timeout=20, headers={"User-Agent": USER_AGENT})
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        return soup.get_text(" ", strip=True)
    except Exception as e:
        print(
            f"ERREUR (ALLOC_AI): Échec fetch Requests sur {url}: {e}", file=sys.stderr
        )
        return None


def _extract_rates_with_gpt(page_text: str) -> dict[str, float | None] | None:
    """Extrait les taux plein et réduit des allocations familiales via GPT."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("ERREUR (ALLOC_AI): Clé OPENAI_API_KEY manquante.", file=sys.stderr)
        return None

    client = OpenAI(api_key=api_key)
    current_year = datetime.now().year
    today = datetime.now().strftime("%d/%m/%Y")

    prompt = (
        f"Aujourd'hui, nous sommes le {today}.\n"
        f"Analyse ce texte issu d'une page potentiellement URSSAF et identifie les taux patronaux "
        f"des allocations familiales applicables en France pour l'année {current_year}.\n"
        "- Il existe deux taux distincts :\n"
        '  1. "taux plein" (ou "droit commun")\n'
        '  2. "taux réduit" (applicable aux rémunérations ≤ 3,5 SMIC)\n\n'
        "Retourne un JSON strict avec ces deux clés et leurs valeurs en pourcentage :\n"
        '{"plein":x.xx,"reduit":x.xx}\n'
        "- Si une valeur est absente, mets null.\n"
        "- Ne renvoie que du JSON valide, sans texte ni explication.\n"
        "- Vérifie que les taux semblent cohérents (entre 2 et 5%).\n"
        "Ne te fie pas à n'importe quel site, ait du recul sur les résultats que tu donnes.\n"
        "Renvoie"
        "Texte à analyser (max 15000 caractères):\n---\n" + page_text[:15000]
    )

    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            response_format={"type": "json_object"},
            temperature=0.1,
            messages=[
                {
                    "role": "system",
                    "content": "Assistant d'extraction JSON pur, spécialisé URSSAF et cotisations sociales.",
                },
                {"role": "user", "content": prompt},
            ],
        )
        data = json.loads(resp.choices[0].message.content.strip())
        plein = data.get("plein")
        reduit = data.get("reduit")

        def to_rate(v):
            if v is None:
                return None
            try:
                return round(float(str(v).replace(",", ".")) / 100.0, 6)
            except Exception:
                return None

        return {"plein": to_rate(plein), "reduit": to_rate(reduit)}

    except Exception as e:
        print(f"ERREUR (ALLOC_AI): Extraction IA échouée: {e}", file=sys.stderr)
        return None


def build_payload(rates: dict[str, float | None] | None, found_url: str | None) -> dict:
    """Construit le JSON final strict demandé."""
    source_url = (
        found_url
        or "https://www.urssaf.fr/accueil/employeur/cotisations/liste-cotisations/allocations-familiales.html"
    )
    source_label = "URSSAF - Allocations familiales"

    plein = rates.get("plein") if rates else None
    reduit = rates.get("reduit") if rates else None

    return {
        "id": "allocations_familiales",
        "type": "cotisation",
        "libelle": "Allocations familiales",
        "base": "brut",
        "valeurs": {
            "salarial": None,
            "patronal_plein": plein,
            "patronal_reduit": reduit,
        },
        "meta": {
            "source": [{"url": source_url, "label": source_label, "date_doc": ""}],
            "scraped_at": iso_now(),
            "generator": "scripts/alloc/alloc_AI.py",
            "method": "ai",
        },
    }


# --- Fonction principale ---


def main() -> None:
    """Orchestre la recherche IA et construit la sortie JSON."""
    current_year = datetime.now().year
    SEARCH_QUERY = SEARCH_QUERY_TEMPLATE.format(year=current_year)
    print(f"INFO (ALLOC_AI): Recherche DDGS: '{SEARCH_QUERY}'", file=sys.stderr)

    results = []
    try:
        search_results = DDGS().text(SEARCH_QUERY, region="fr-fr", max_results=10)
        if search_results:
            results = [
                r["href"]
                for r in search_results
                if "urssaf.fr" in r["href"] or "service-public.fr" in r["href"]
            ]
        if not results:
            print(
                "ERREUR (ALLOC_AI): Aucun résultat URSSAF trouvé, fallback vers tous domaines.",
                file=sys.stderr,
            )
            search_results = DDGS().text(SEARCH_QUERY, region="fr-fr", max_results=10)
            results = [r["href"] for r in search_results]
    except Exception as e:
        print(f"ERREUR (ALLOC_AI): Échec recherche DDGS: {e}", file=sys.stderr)

    rates = None
    successful_url = None

    for url in results:
        print(f"INFO (ALLOC_AI): Analyse URL: {url}", file=sys.stderr)
        txt = _fetch_text_with_requests(url)
        if not txt:
            continue

        rates = _extract_rates_with_gpt(txt)
        if rates and (
            rates.get("plein") is not None or rates.get("reduit") is not None
        ):
            print(
                f"✅ Taux trouvés: plein={rates.get('plein')} reduit={rates.get('reduit')}",
                file=sys.stderr,
            )
            successful_url = url
            break
        else:
            print(
                "INFO (ALLOC_AI): Données non valides, URL suivante.", file=sys.stderr
            )
        time.sleep(1)

    if rates is None:
        print("ERREUR (ALLOC_AI): Aucune donnée valide extraite.", file=sys.stderr)

    payload = build_payload(rates, successful_url)
    print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
