# scripts/CFP/CFP_AI.py

#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
CFP_AI.py
Recherche les taux de la Contribution à la Formation Professionnelle (CFP)
pour les entreprises de moins de 11 salariés et de 11 salariés et plus.
Analyse des pages via DDGS/BeautifulSoup, puis extraction IA (GPT).
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
    "taux contribution formation professionnelle CFP URSSAF "
    "{year} moins de 11 salariés 11 et plus site:urssaf.fr OR site:legisocial.fr"
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
    """Récupère le texte brut d'une page web via requests/BeautifulSoup."""
    try:
        r = requests.get(url, timeout=15, headers={"User-Agent": USER_AGENT})
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        return soup.get_text(" ", strip=True)
    except Exception as e:
        print(f"ERREUR (CFP_AI): Échec fetch Requests sur {url}: {e}", file=sys.stderr)
        return None


def _extract_rates_with_gpt(page_text: str) -> dict[str, float | None] | None:
    """Demande au modèle d'extraire les deux taux CFP."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("ERREUR (CFP_AI): Clé OPENAI_API_KEY manquante.", file=sys.stderr)
        return None

    client = OpenAI(api_key=api_key)
    current_year = datetime.now().year

    prompt = (
        f"Analyse ce texte pour extraire les taux de la Contribution à la Formation Professionnelle (CFP) "
        f"applicables en France pour l'année {current_year}.\n"
        "- Deux taux sont attendus :\n"
        '  1. \"taux_moins_11\" (moins de 11 salariés)\n'
        '  2. \"taux_11_et_plus\" (11 salariés et plus)\n\n'
        "Retourne un JSON strict avec ces deux clés et leurs valeurs en pourcentage (ex: 0.55 ou 1.0) :\n"
        "{\n"
        '  \"taux_moins_11\": <float|null>,\n'
        '  \"taux_11_et_plus\": <float|null>\n'
        "}\n"
        "- Toutes les clés doivent être présentes.\n"
        "- Si une valeur est absente, mets null.\n"
        "- Ne renvoie que du JSON pur.\n"
        "Vérifie bien que la source soit fiable, et prend du recul. Choisi les valeurs comme si t'étais un humain qui lisait l'article.\n\n"
        "Texte à analyser (max 15000 caractères):\n---\n"
        + page_text[:15000]
    )

    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            response_format={"type": "json_object"},
            temperature=0,
            messages=[
                {"role": "system", "content": "Assistant d'extraction JSON pur pour les taux CFP."},
                {"role": "user", "content": prompt},
            ],
        )
        data = json.loads(resp.choices[0].message.content.strip())
        return {
            "taux_moins_11": data.get("taux_moins_11"),
            "taux_11_et_plus": data.get("taux_11_et_plus"),
        }

    except Exception as e:
        print(f"ERREUR (CFP_AI): Extraction IA échouée: {e}", file=sys.stderr)
        return None


def build_payload(rates: dict[str, float | None] | None, found_url: str | None) -> dict:
    """Construit la charge utile JSON finale pour l'orchestrateur."""
    def _to_rate(val):
        if val is None:
            return None
        try:
            return round(float(str(val).replace(",", ".")) / 100.0, 6)
        except Exception:
            return None

    taux_moins_11 = _to_rate(rates.get("taux_moins_11")) if rates else None
    taux_11_et_plus = _to_rate(rates.get("taux_11_et_plus")) if rates else None

    source_url = found_url or "https://www.urssaf.fr/accueil/employeur/cotisations/liste-cotisations/formation-professionnelle.html"
    source_label = "URSSAF - Contribution à la formation professionnelle"

    return {
        "id": "cfp",
        "type": "cotisation",
        "libelle": "Contribution à la Formation Professionnelle (CFP)",
        "sections": {
            "salarial": None,
            "patronal_moins_11": taux_moins_11,
            "patronal_11_et_plus": taux_11_et_plus,
        },
        "meta": {
            "source": [
                {"url": source_url, "label": source_label, "date_doc": ""}
            ],
            "scraped_at": iso_now(),
            "generator": "scripts/CFP/CFP.py",
            "method": "primary",
        },
    }


def main() -> None:
    """Orchestre la recherche et l'extraction des deux taux CFP via l'IA."""
    current_year = datetime.now().year
    SEARCH_QUERY = SEARCH_QUERY_TEMPLATE.format(year=current_year)
    print(f"INFO (CFP_AI): Démarrage. Recherche DDGS: '{SEARCH_QUERY}'", file=sys.stderr)

    results = []
    try:
        search_results = DDGS().text(SEARCH_QUERY, region="fr-fr", max_results=10)
        if search_results:
            results = [r["href"] for r in search_results]
        if not results:
            print("ERREUR (CFP_AI): DDGS n'a retourné aucun résultat.", file=sys.stderr)
    except Exception as e:
        print(f"ERREUR (CFP_AI): Échec de la recherche DuckDuckGo: {e}", file=sys.stderr)

    rates = None
    successful_url = None

    for url in results:
        print(f"INFO (CFP_AI): Analyse URL: {url}", file=sys.stderr)
        txt = _fetch_text_with_requests(url)
        if not txt:
            print("INFO (CFP_AI): ...Échec fetch ou texte vide.", file=sys.stderr)
            continue

        rates = _extract_rates_with_gpt(txt)
        if rates and (rates.get("taux_moins_11") is not None or rates.get("taux_11_et_plus") is not None):
            print(
                f"INFO (CFP_AI): Taux trouvés sur cette URL: "
                f"moins_11={rates.get('taux_moins_11')} plus_11={rates.get('taux_11_et_plus')}",
                file=sys.stderr,
            )
            successful_url = url
            break
        else:
            print("INFO (CFP_AI): ...Taux non trouvés sur cette URL.", file=sys.stderr)

    if rates is None:
        print("ERREUR (CFP_AI): Aucun taux trouvé après analyse.", file=sys.stderr)
        rates = {}

    payload = build_payload(rates, successful_url)
    print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()

