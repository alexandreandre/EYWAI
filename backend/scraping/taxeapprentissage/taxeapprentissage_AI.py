# scripts/taxeapprentissage/taxeapprentissage_AI.py

#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
taxeapprentissage_AI.py
Recherche les taux de la taxe d'apprentissage (part principale et solde)
sur le web via DDGS, analyse les pages avec 'requests' et 'BeautifulSoup',
et utilise l'IA (GPT) pour extraire les taux officiels métropole/Alsace-Moselle.
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

SEARCH_QUERY_TEMPLATE = "taux taxe d'apprentissage URSSAF {year}"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36"
)

# --- Fonctions utilitaires ---

def iso_now() -> str:
    """Retourne l'heure actuelle au format ISO UTC."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _fetch_text_with_requests(url: str) -> str | None:
    """Récupère le texte brut d'une page via requests et BeautifulSoup."""
    try:
        r = requests.get(url, timeout=15, headers={"User-Agent": USER_AGENT})
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        return soup.get_text(" ", strip=True)
    except Exception as e:
        print(f"ERREUR (TAXEAPP_AI): échec fetch sur {url}: {e}", file=sys.stderr)
        return None


def _extract_rates_with_gpt(page_text: str) -> dict | None:
    """Extrait la part principale et le solde via GPT."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("ERREUR (TAXEAPP_AI): clé OPENAI_API_KEY manquante.", file=sys.stderr)
        return None

    client = OpenAI(api_key=api_key)
    current_year = datetime.now().year

    prompt = (
        f"Analyse ce texte et extrait les taux de la taxe d'apprentissage applicables en {current_year}.\n"
        "Je veux la décomposition suivante :\n"
        "- 'part_principale' (taux métropole et taux Alsace-Moselle)\n"
        "- 'solde' (taux métropole et taux Alsace-Moselle)\n"
        "Si un taux n’existe pas, mets 0.\n"
        "Réponds uniquement en JSON strict du format suivant :\n"
        "{\n"
        '  "part_principale": {"taux_metropole": 0.59, "taux_alsace_moselle": 0.44},\n'
        '  "solde": {"taux_metropole": 0.09, "taux_alsace_moselle": 0.0}\n'
        "}\n"
        "Aucune explication. Uniquement le JSON.\n\n"
        "Texte à analyser (max 15000 caractères):\n---\n"
        + page_text[:15000]
    )

    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            response_format={"type": "json_object"},
            temperature=0,
            messages=[
                {"role": "system", "content": "Assistant d'extraction JSON pur, spécialisé URSSAF."},
                {"role": "user", "content": prompt},
            ],
        )
        data = json.loads(resp.choices[0].message.content.strip())
        return data
    except Exception as e:
        print(f"ERREUR (TAXEAPP_AI): extraction IA échouée: {e}", file=sys.stderr)
        return None


def build_payload(rates: dict | None, found_url: str | None) -> dict:
    """Construit la charge utile JSON finale dans le format strict."""
    def _to_rate(val):
        if val is None:
            return None
        try:
            return round(float(str(val).replace(",", ".")) / 100.0, 6)
        except Exception:
            return None

    part_principale = rates.get("part_principale") if rates else {}
    solde = rates.get("solde") if rates else {}

    # Conversion des pourcentages en taux
    part_principale = {
        "taux_metropole": _to_rate(part_principale.get("taux_metropole")),
        "taux_alsace_moselle": _to_rate(part_principale.get("taux_alsace_moselle")),
    }
    solde = {
        "taux_metropole": _to_rate(solde.get("taux_metropole")),
        "taux_alsace_moselle": _to_rate(solde.get("taux_alsace_moselle")),
    }

    total = {
        "taux_metropole": (
            (part_principale["taux_metropole"] or 0)
            + (solde["taux_metropole"] or 0)
        ),
        "taux_alsace_moselle": (
            (part_principale["taux_alsace_moselle"] or 0)
            + (solde["taux_alsace_moselle"] or 0)
        ),
    }

    source_url = found_url or "N/A"
    source_label = "Source IA (via DDGS)" if found_url else "N/A (Taux non trouvé par l'IA)"

    return {
        "id": "taxe_apprentissage",
        "type": "cotisation",
        "libelle": "Taxe d'Apprentissage",
        "sections": {
            "salarial": None,
            "part_principale": part_principale,
            "solde": solde,
            "total": total,
        },
        "meta": {
            "source": [{"url": source_url, "label": source_label, "date_doc": ""}],
            "scraped_at": iso_now(),
            "generator": "scripts/taxeapprentissage/taxeapprentissage_AI.py",
            "method": "ai",
        },
    }


def main() -> None:
    """Orchestre la recherche et l'extraction IA."""
    current_year = datetime.now().year
    SEARCH_QUERY = SEARCH_QUERY_TEMPLATE.format(year=current_year)
    print(f"INFO (TAXEAPP_AI): Recherche DDGS: '{SEARCH_QUERY}'", file=sys.stderr)

    results = []
    try:
        search_results = DDGS().text(SEARCH_QUERY, region="fr-fr", max_results=5)
        if search_results:
            results = [r["href"] for r in search_results]
        if not results:
            print("ERREUR (TAXEAPP_AI): DDGS n'a retourné aucun résultat.", file=sys.stderr)
    except Exception as e:
        print(f"ERREUR (TAXEAPP_AI): Échec recherche DuckDuckGo: {e}", file=sys.stderr)

    final_rates = None
    successful_url = None

    for url in results:
        print(f"INFO (TAXEAPP_AI): Analyse URL: {url}", file=sys.stderr)
        txt = _fetch_text_with_requests(url)
        if not txt:
            continue

        rates = _extract_rates_with_gpt(txt)
        if (
            rates
            and "part_principale" in rates
            and "solde" in rates
            and "taux_metropole" in rates["part_principale"]
            and "taux_alsace_moselle" in rates["part_principale"]
            and "taux_metropole" in rates["solde"]
            and "taux_alsace_moselle" in rates["solde"]
        ):
            print("✅ Structure complète extraite avec succès.", file=sys.stderr)
            final_rates = rates
            successful_url = url
            break
        else:
            print("INFO (TAXEAPP_AI): Données incomplètes, passage à l'URL suivante.", file=sys.stderr)
        time.sleep(1)

    if final_rates is None:
        print("ERREUR (TAXEAPP_AI): Aucune donnée valide extraite.", file=sys.stderr)

    payload = build_payload(final_rates, successful_url)
    print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
