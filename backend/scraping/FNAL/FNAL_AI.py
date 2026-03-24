# scripts/FNAL/FNAL_AI.py

#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
FNAL_AI.py
Recherche les taux du Fonds National d’Aide au Logement (FNAL)
pour les entreprises de moins de 50 salariés et de 50 salariés et plus,
via DDGS, puis extraction IA (GPT) à la date du jour.
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

load_dotenv()

SEARCH_QUERY_TEMPLATE = (
    "taux cotisation FNAL URSSAF {year}"
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
        print(f"ERREUR (FNAL_AI): Échec fetch Requests sur {url}: {e}", file=sys.stderr)
        return None


def _extract_rates_with_gpt(page_text: str) -> dict[str, float | None]:
    """Demande au modèle d'extraire les deux taux FNAL en vigueur aujourd’hui."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("ERREUR (FNAL_AI): Clé OPENAI_API_KEY manquante.", file=sys.stderr)
        return {"patronal_moins_50": None, "patronal_50_et_plus": None}

    client = OpenAI(api_key=api_key)
    current_year = datetime.now().year
    today_str = datetime.now().strftime("%A %d %B %Y")

    prompt = (
        f"Nous sommes le {today_str}. "
        f"Analyse attentivement le texte ci-dessous et identifie les taux officiels en vigueur à cette date "
        f"pour la 'cotisation FNAL' (Fonds National d’Aide au Logement) en France, applicables aux employeurs.\n\n"
        "Deux taux distincts existent :\n"
        "1. Entreprises de MOINS de 50 salariés.\n"
        "2. Entreprises de 50 salariés ET PLUS.\n\n"
        "Ne considère que les taux généraux actuellement applicables au régime général. "
        "Ignore les valeurs historiques, exceptions, ou cas particuliers.\n\n"
        "Renvoie uniquement un JSON strict au format suivant :\n"
        "{\n"
        '  \"taux_moins_50\": <float|null>,\n'
        '  \"taux_50_et_plus\": <float|null>\n'
        "}\n"
        "- Les valeurs doivent être en pourcentage (ex: 0.10 pour 0,10%).\n"
        "- Si tu ne trouves pas une valeur actuelle, mets null.\n"
        "- Ne renvoie que du JSON pur sans texte additionnel.\n\n"
        "Texte à analyser (max 15000 caractères) :\n---\n"
        + page_text[:15000]
    )

    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            response_format={"type": "json_object"},
            temperature=0,
            messages=[
                {"role": "system", "content": "Assistant d'extraction JSON pur, expert en législation sociale française."},
                {"role": "user", "content": prompt},
            ],
        )
        data = json.loads(resp.choices[0].message.content.strip())

        def _to_rate(v):
            if v is None:
                return None
            try:
                return round(float(str(v).replace(",", ".")) / 100.0, 6)
            except Exception:
                return None

        return {
            "patronal_moins_50": _to_rate(data.get("taux_moins_50")),
            "patronal_50_et_plus": _to_rate(data.get("taux_50_et_plus")),
        }
    except Exception as e:
        print(f"ERREUR (FNAL_AI): Extraction IA échouée: {e}", file=sys.stderr)
        return {"patronal_moins_50": None, "patronal_50_et_plus": None}


def build_payload(rates: dict, found_url: str | None) -> dict:
    """Construit la charge utile JSON finale."""
    source_url = (
        found_url
        or "https://www.urssaf.fr/accueil/outils-documentation/taux-baremes/taux-cotisations-secteur-prive.html"
    )
    source_label = "URSSAF — Taux secteur privé"

    return {
        "id": "fnal",
        "type": "cotisation",
        "libelle": "Fonds National d’Aide au Logement (FNAL)",
        "sections": {
            "salarial": None,
            "patronal_moins_50": rates.get("patronal_moins_50"),
            "patronal_50_et_plus": rates.get("patronal_50_et_plus"),
        },
        "meta": {
            "source": [{"url": source_url, "label": source_label, "date_doc": ""}],
            "scraped_at": iso_now(),
            "generator": "scripts/FNAL/FNAL.py",
            "method": "primary",
        },
    }


def main() -> None:
    """Orchestre la recherche et l'extraction des taux FNAL."""
    current_year = datetime.now().year
    SEARCH_QUERY = SEARCH_QUERY_TEMPLATE.format(year=current_year)
    print(f"INFO (FNAL_AI): Démarrage. Recherche DDGS: '{SEARCH_QUERY}'", file=sys.stderr)

    results = []
    try:
        search_results = DDGS().text(SEARCH_QUERY, region="fr-fr", max_results=10)
        if search_results:
            results = [r["href"] for r in search_results]
        if not results:
            print("ERREUR (FNAL_AI): DDGS n'a retourné aucun résultat.", file=sys.stderr)
    except Exception as e:
        print(f"ERREUR (FNAL_AI): Échec de la recherche DDGS: {e}", file=sys.stderr)

    final_rates, successful_url = None, None

    for url in results:
        print(f"INFO (FNAL_AI): Analyse URL: {url}", file=sys.stderr)
        txt = _fetch_text_with_requests(url)
        if not txt:
            print("INFO (FNAL_AI): ...Échec fetch ou texte vide.", file=sys.stderr)
            continue

        rates = _extract_rates_with_gpt(txt)
        if rates.get("patronal_moins_50") is not None and rates.get("patronal_50_et_plus") is not None:
            print(f"INFO (FNAL_AI): Taux trouvés sur {url}", file=sys.stderr)
            final_rates = rates
            successful_url = url
            break

    if not final_rates:
        print("ERREUR (FNAL_AI): Aucun taux trouvé après analyse.", file=sys.stderr)
        final_rates = {"patronal_moins_50": None, "patronal_50_et_plus": None}

    payload = build_payload(final_rates, successful_url)
    print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
