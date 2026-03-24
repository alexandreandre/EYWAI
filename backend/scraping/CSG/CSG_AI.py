# scripts/CSG/CSG_AI.py

#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
CSG_AI.py
Recherche les taux de la CSG/CRDS sur le web via DDGS,
analyse les pages avec 'requests' et 'BeautifulSoup',
et utilise l'IA (GPT) pour extraire les taux officiels applicables à la date du jour.
"""

import json
import os
import sys
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from dotenv import load_dotenv
from ddgs.ddgs import DDGS
from openai import OpenAI

load_dotenv()

SEARCH_QUERY_TEMPLATE = (
    "taux CSG CRDS salarié site:urssaf.fr {year}"
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
        print(f"ERREUR (CSG_AI): Échec fetch Requests sur {url}: {e}", file=sys.stderr)
        return None


def _extract_json_with_gpt(page_text: str) -> dict | None:
    """Extrait les taux CSG/CRDS depuis le texte via GPT, en cherchant la valeur réellement en vigueur aujourd’hui."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("ERREUR (CSG_AI): Clé OPENAI_API_KEY manquante.", file=sys.stderr)
        return None

    client = OpenAI(api_key=api_key)
    current_year = datetime.now().year
    today_str = datetime.now().strftime("%A %d %B %Y")

    prompt = (
        f"Nous sommes le {today_str}. "
        f"Analyse attentivement ce texte provenant du site officiel URSSAF et identifie les taux de la 'CSG' et de la 'CRDS' "
        f"réellement en vigueur à cette date ({today_str}), pour les salariés du secteur privé en France.\n\n"
        "Ne prends en compte que les informations issues de l'URSSAF ou des textes réglementaires explicites. "
        "Ignore tout ce qui concerne des taux historiques, des cas particuliers (fonction publique, artistes, remplaçants, etc.) "
        "ou des taux erronés provenant d'autres sources.\n\n"
        "Extrait les trois valeurs suivantes :\n"
        "1. 'csg_imposable' → part non déductible (imposable sur le revenu)\n"
        "2. 'csg_non_imposable' → part déductible\n"
        "3. 'crds' → taux CRDS\n\n"
        "Renvoie un JSON strict au format :\n"
        "{\n"
        '  \"csg_imposable\": <float|null>,\n'
        '  \"csg_non_imposable\": <float|null>,\n'
        '  \"crds\": <float|null>\n'
        "}\n"
        "- Valeurs en pourcentage (ex: 2.40 pour 2,40%).\n"
        "- Si aucune donnée trouvée, mets null.\n"
        "- Ne renvoie que du JSON pur, sans explication ni commentaire.\n\n"
        "Texte à analyser (max 15000 caractères) :\n---\n"
        + page_text[:15000]
    )

    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            response_format={"type": "json_object"},
            temperature=0,
            messages=[
                {"role": "system", "content": "Assistant d'extraction JSON expert en droit social français, spécialisé en paie et URSSAF."},
                {"role": "user", "content": prompt},
            ],
        )
        data = json.loads(resp.choices[0].message.content.strip())
        return {
            "csg_imposable": data.get("csg_imposable"),
            "csg_non_imposable": data.get("csg_non_imposable"),
            "crds": data.get("crds"),
        }
    except Exception as e:
        print(f"ERREUR (CSG_AI): Extraction IA échouée: {e}", file=sys.stderr)
        return None


def build_payload(taux: dict | None, found_url: str | None) -> dict:
    """Construit la charge utile JSON finale."""
    salarial = {"deductible": None, "non_deductible": None}
    patronal = None

    if taux:
        try:
            deductible = float(str(taux.get("csg_non_imposable")).replace(",", ".")) / 100.0
        except Exception:
            deductible = None
        try:
            non_deductible = (
                float(str(taux.get("csg_imposable")).replace(",", ".")) / 100.0
                + float(str(taux.get("crds")).replace(",", ".")) / 100.0
            )
        except Exception:
            non_deductible = None

        salarial = {
            "deductible": round(deductible, 6) if deductible else None,
            "non_deductible": round(non_deductible, 6) if non_deductible else None,
        }

    source_url = (
        found_url
        or "https://www.urssaf.fr/accueil/outils-documentation/taux-baremes/taux-cotisations-secteur-prive.html"
    )
    source_label = "URSSAF — Taux secteur privé"

    return {
        "id": "csg",
        "type": "cotisation",
        "libelle": "CSG/CRDS",
        "base": "brut",
        "valeurs": {"salarial": salarial, "patronal": patronal},
        "meta": {
            "source": [{"url": source_url, "label": source_label, "date_doc": ""}],
            "scraped_at": iso_now(),
            "generator": "scripts/CSG/CSG.py",
            "method": "primary",
        },
    }


def main() -> None:
    current_year = datetime.now().year
    SEARCH_QUERY = SEARCH_QUERY_TEMPLATE.format(year=current_year)
    print(f"INFO (CSG_AI): Démarrage. Recherche DDGS sur URSSAF uniquement: '{SEARCH_QUERY}'", file=sys.stderr)

    results = []
    try:
        search_results = DDGS().text(SEARCH_QUERY, region="fr-fr", max_results=10)
        if search_results:
            results = [r["href"] for r in search_results if "urssaf.fr" in r.get("href", "")]
        if not results:
            print("ERREUR (CSG_AI): Aucun résultat URSSAF trouvé.", file=sys.stderr)
    except Exception as e:
        print(f"ERREUR (CSG_AI): Échec de la recherche DDGS: {e}", file=sys.stderr)

    taux, successful_url = None, None

    for url in results:
        print(f"INFO (CSG_AI): Analyse URL URSSAF: {url}", file=sys.stderr)
        txt = _fetch_text_with_requests(url)
        if not txt:
            print("INFO (CSG_AI): ...Échec fetch ou texte vide.", file=sys.stderr)
            continue

        data = _extract_json_with_gpt(txt)
        if not data:
            continue

        if all(data.get(k) is not None for k in ("csg_imposable", "csg_non_imposable", "crds")):
            taux = data
            successful_url = url
            break

    if taux is None:
        print("ERREUR (CSG_AI): Aucun taux trouvé après analyse.", file=sys.stderr)

    payload = build_payload(taux, successful_url)
    print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
