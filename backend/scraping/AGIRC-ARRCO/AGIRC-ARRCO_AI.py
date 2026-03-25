#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
AGIRC-ARRCO_AI.py
Recherche les taux de cotisations AGIRC-ARRCO pour l'année courante
sur URSSAF, LegiSocial ou Service-Public, puis extrait les valeurs
via GPT (JSON strict).
"""

import json
import os
import re
import sys
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from ddgs.ddgs import DDGS
from openai import OpenAI

load_dotenv()
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/108.0 Safari/537.36"
EXPECTED_KEYS = [
    "retraite_comp_t1_salarial",
    "retraite_comp_t1_patronal",
    "retraite_comp_t2_salarial",
    "retraite_comp_t2_patronal",
    "ceg_t1_salarial",
    "ceg_t1_patronal",
    "ceg_t2_salarial",
    "ceg_t2_patronal",
    "cet_salarial",
    "cet_patronal",
    "apec_salarial",
    "apec_patronal",
]

TRUSTED_DOMAINS = ["urssaf.fr", "legisocial.fr", "service-public.fr", "agirc-arrco.fr"]

# ---------------------------------------------------


def iso_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def clean_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text)
    text = re.sub(
        r"(cookies?|accepter|navigation|menu|pied de page).*", "", text, flags=re.I
    )
    return text.strip()


def fetch_page_text(url: str) -> str | None:
    try:
        r = requests.get(url, timeout=15, headers={"User-Agent": USER_AGENT})
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        return clean_text(soup.get_text(" ", strip=True))
    except Exception as e:
        print(f"ERREUR fetch {url}: {e}", file=sys.stderr)
        return None


def extract_rates_with_gpt(page_text: str) -> dict[str, float | None] | None:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("ERREUR: OPENAI_API_KEY manquante.", file=sys.stderr)
        return None
    client = OpenAI(api_key=api_key)
    year = datetime.now().year

    prompt = (
        f"Extrait du texte ci-dessous les taux AGIRC-ARRCO applicables en {year}. "
        "Renvoie uniquement un JSON strict avec les clés suivantes et les valeurs en % (ex: 3.15 pour 3.15%) :\n"
        + json.dumps({k: None for k in EXPECTED_KEYS}, indent=2)
        + "\nTexte :\n"
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
                    "content": "Assistant d'extraction JSON pour taux AGIRC-ARRCO.",
                },
                {"role": "user", "content": prompt},
            ],
        )
        data = json.loads(resp.choices[0].message.content)
        out = {}
        for k in EXPECTED_KEYS:
            v = data.get(k)
            try:
                out[k] = (
                    round(float(str(v).replace(",", ".")) / 100.0, 6)
                    if v not in (None, "", "null")
                    else None
                )
            except Exception:
                out[k] = None
        return out
    except Exception as e:
        print(f"ERREUR GPT: {e}", file=sys.stderr)
        return None


def build_payload(bundle: dict | None, url: str | None) -> dict:
    """
    Produit un JSON identique à celui du scraper AGIRC-ARRCO.py,
    mais en utilisant les valeurs extraites par GPT.
    """
    items = []
    if bundle:

        def add(id_, libelle, base, s, p):
            return {
                "id": id_,
                "libelle": libelle,
                "base": base,
                "valeurs": {"salarial": bundle.get(s), "patronal": bundle.get(p)},
            }

        items = [
            add(
                "retraite_comp_t1",
                "Retraite Complémentaire Tranche 1 (AGIRC-ARRCO)",
                "plafond_ss",
                "retraite_comp_t1_salarial",
                "retraite_comp_t1_patronal",
            ),
            add(
                "retraite_comp_t2",
                "Retraite Complémentaire Tranche 2 (AGIRC-ARRCO)",
                "tranche_2",
                "retraite_comp_t2_salarial",
                "retraite_comp_t2_patronal",
            ),
            add(
                "ceg_t1",
                "Contribution d'Équilibre Général (CEG) T1",
                "plafond_ss",
                "ceg_t1_salarial",
                "ceg_t1_patronal",
            ),
            add(
                "ceg_t2",
                "Contribution d'Équilibre Général (CEG) T2",
                "tranche_2",
                "ceg_t2_salarial",
                "ceg_t2_patronal",
            ),
            add(
                "cet",
                "Contribution d'Équilibre Technique (CET)",
                "brut_sup_plafond",
                "cet_salarial",
                "cet_patronal",
            ),
            add(
                "apec",
                "Cotisation APEC (Cadres)",
                "brut_cadre_4_plafonds",
                "apec_salarial",
                "apec_patronal",
            ),
        ]

    return {
        "id": "agirc_arrco_bundle",
        "type": "cotisation_bundle",
        "items": items,
        "meta": {
            "source": [
                {"url": url or "N/A", "label": "Agirc-Arrco", "date_doc": iso_now()}
            ],
            "generator": "scripts/AGIRC-ARRCO/AGIRC-ARRCO_AI.py",
        },
    }


# ---------------------------------------------------


def search_trusted_links(year: int) -> list[str]:
    query = f"taux cotisation AGIRC-ARRCO URSSAF site:urssaf.fr OR site:legisocial.fr OR site:service-public.fr {year}"
    print(f"Recherche DDGS : {query}", file=sys.stderr)
    urls = []
    try:
        for r in DDGS().text(query, region="fr-fr", max_results=10):
            href = r.get("href", "")
            if any(domain in href for domain in TRUSTED_DOMAINS):
                urls.append(href)
    except Exception as e:
        print(f"ERREUR recherche DDGS: {e}", file=sys.stderr)

    if not urls:
        # Fallback manuel sur pages connues
        urls = [
            "https://www.urssaf.fr/portail/home/employeur/reduire-ou-augmenter-leffectif/les-taux-de-cotisations.html",
            "https://www.legisocial.fr/taux-social-salarial-patronal/retraite-complementaire-agirc-arrco.html",
        ]
    return urls


def main():
    year = datetime.now().year
    urls = search_trusted_links(year)

    found_rates, found_url = None, None
    for url in urls:
        print(f"Analyse de {url}", file=sys.stderr)
        text = fetch_page_text(url)
        if not text or "AGIRC" not in text.upper():
            continue
        rates = extract_rates_with_gpt(text)
        if rates and any(v is not None for v in rates.values()):
            found_rates, found_url = rates, url
            break

    payload = build_payload(found_rates, found_url)
    print(json.dumps(payload, ensure_ascii=False))
    sys.exit(0 if found_rates else 2)


if __name__ == "__main__":
    main()
