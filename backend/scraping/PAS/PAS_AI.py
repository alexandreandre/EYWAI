# scripts/PAS/PAS_AI.py

import json
import os
import re
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from openai import OpenAI
from ddgs.ddgs import DDGS  # plus stable que googlesearch

load_dotenv()

PREFERRED_URL = "https://bofip.impots.gouv.fr/bofip/11255-PGP.html/identifiant%3DBOI-BAREME-000037-20250410"
SEARCH_QUERY = "barème taux neutre prélèvement à la source BOFiP site:bofip.impots.gouv.fr"

NBSP = "\xa0"
NNBSP = "\u202f"
THIN = "\u2009"


# --- Utils ---
def iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _to_float(x: Any) -> Optional[float]:
    if x is None:
        return None
    if isinstance(x, (int, float)):
        return float(x)
    s = str(x).strip().replace(NBSP, "").replace(NNBSP, "").replace(THIN, "").replace(" ", "").replace(",", ".")
    m = re.search(r"-?\d+(?:\.\d+)?", s)
    return float(m.group(0)) if m else None


def _download(url: str) -> str:
    r = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    return r.text


def extract_json_with_gpt(page_text: str) -> Optional[Dict[str, Any]]:
    """Extraction du barème via GPT."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("ERREUR : OPENAI_API_KEY absente.", file=sys.stderr)
        return None
    client = OpenAI(api_key=api_key)
    current_year = datetime.now().year
    current_date = datetime.now().strftime("%d/%m/%Y")

    prompt = f"""
Tu es un expert fiscal français.
Analyse le texte suivant (issu du BOFiP) et extrais UNIQUEMENT le barème mensuel du taux neutre du prélèvement à la source pour l'année {current_year}.
Date actuelle : {current_date}.

Tu dois identifier les tranches pour :
1) "metropole" (métropole et hors de France)
2) "grm" (Guadeloupe, Réunion, Martinique)
3) "gm" (Guyane, Mayotte)

Format de sortie STRICT :
{{
  "metropole": [{{"plafond": 1620.0, "taux": 0.0}}, ..., {{"plafond": null, "taux": 43.0}}],
  "grm": [...],
  "gm": [...]
}}

- Tous les montants en euros (nombre décimal)
- Tous les taux en pourcentages (nombre décimal, sans le signe %)
- Aucune explication hors JSON.
Texte à analyser :
---
{page_text[:15000]}
---
""".strip()

    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            response_format={"type": "json_object"},
            temperature=0,
            messages=[
                {"role": "system", "content": "Assistant d’extraction de données fiscales. Réponds uniquement en JSON valide."},
                {"role": "user", "content": prompt},
            ],
        )
        raw = resp.choices[0].message.content.strip()
        return json.loads(raw)
    except Exception as e:
        print(f"ERREUR extraction IA : {e}", file=sys.stderr)
        return None


# --- Core ---
def get_pas_baremes_via_ai() -> Optional[Dict[str, List[Dict[str, Any]]]]:
    """Cherche la page BOFiP et extrait le barème complet."""
    candidates = [PREFERRED_URL]

    try:
        print(f"Recherche DDGS : {SEARCH_QUERY}", file=sys.stderr)
        for r in DDGS().text(SEARCH_QUERY, max_results=5):
            url = r.get("href")
            if url and "bofip.impots.gouv.fr" in url and url not in candidates:
                candidates.append(url)
    except Exception as e:
        print(f"   - ERREUR de recherche : {e}", file=sys.stderr)

    for url in candidates:
        print(f"\n--- Analyse de {url} ---", file=sys.stderr)
        try:
            html = _download(url)
            soup = BeautifulSoup(html, "html.parser")
            text = soup.get_text(" ", strip=True)
            data = extract_json_with_gpt(text)
            if not data:
                continue

            key_map = {
                "metropole": "metropole",
                "grm": "guadeloupe_reunion_martinique",
                "gm": "guyane_mayotte",
            }
            result = {}
            valid = True
            for src, dst in key_map.items():
                tranches = data.get(src)
                if not isinstance(tranches, list) or not tranches:
                    valid = False
                    break
                conv = []
                for t in tranches:
                    taux = _to_float(t.get("taux"))
                    if taux is None:
                        valid = False
                        break
                    plafond = _to_float(t.get("plafond"))
                    conv.append({"plafond": plafond, "taux": round(taux / 100.0, 5)})
                result[dst] = conv
            if valid:
                return result
        except Exception as e:
            print(f"   - ERREUR lecture page : {e}", file=sys.stderr)

    return None


# --- Main ---
def main():
    data = get_pas_baremes_via_ai()
    if data is None:
        print("ERREUR CRITIQUE : aucun barème trouvé.", file=sys.stderr)
        sys.exit(1)

    payload = {
        "id": "pas_taux_neutre",
        "type": "bareme_imposition",
        "libelle": "Prélèvement à la Source (PAS) - Grille de taux par défaut",
        "sections": data,
        "meta": {
            "source": [
                {
                    "url": PREFERRED_URL,
                    "label": "BOFIP - Barème du prélèvement à la source",
                    "date_doc": "",
                }
            ],
            "scraped_at": iso_now(),
            "generator": "scripts/PAS/PAS_AI.py",
            "method": "ai",
        },
    }

    print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
