# scripts/PSS/PSS.py

import json
import re
import sys
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

URL_URSSAF = "https://www.urssaf.fr/accueil/outils-documentation/taux-baremes/plafonds-securite-sociale.html"

# --- UTILITAIRES ---


def get_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=2,
        status_forcelist=[429, 500, 502, 503, 504],
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": (
                "text/html,application/xhtml+xml,"
                "application/xml;q=0.9,*/*;q=0.8"
            ),
            "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
        }
    )
    return session


def iso_now() -> str:
    """Retourne la date et l'heure actuelles au format ISO 8601 UTC."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_montant(texte: str) -> float:
    """Convertit '1 823,03 €' ou '1\xa0823,03 €' en 1823.03 (aligné sur SMIC.py)."""
    cleaned = (
        texte.replace("\xa0", "")
        .replace("\u202f", "")
        .replace(" ", "")
        .replace("\u2009", "")
        .strip()
    )
    cleaned = cleaned.replace(",", ".")
    match = re.search(r"\d+\.?\d*", cleaned)
    if match:
        return float(match.group())
    return 0.0


def extract_pss_data(soup: BeautifulSoup) -> dict:
    """
    Extrait les plafonds SS depuis les tableaux URSSAF.
    Prend le premier bloc avec "Année" > 40000.
    """
    rows = soup.find_all("tr")

    annuel = None
    trimestriel = None
    mensuel = None
    quinzaine = None
    hebdomadaire = None
    journalier = None
    horaire = None
    annee = datetime.now().year

    for tr in rows:
        text = tr.get_text(strip=True, separator=" | ")
        tds = tr.find_all(["td", "th"])

        if re.match(r"^\d{4}$", text.strip()):
            try:
                annee = int(text.strip())
            except ValueError:
                pass
            continue

        if "Année" in text and annuel is None:
            for td in tds:
                val = parse_montant(td.get_text())
                if val > 40000:
                    annuel = int(val)
                    break

        if "Trimestre" in text and trimestriel is None:
            for td in tds:
                val = parse_montant(td.get_text())
                if val > 5000:
                    trimestriel = int(val)
                    break

        if "Mois" in text and mensuel is None:
            for td in tds:
                val = parse_montant(td.get_text())
                if val > 1000:
                    mensuel = int(val)
                    break

        if "Quinzaine" in text and quinzaine is None:
            for td in tds:
                val = parse_montant(td.get_text())
                if val > 500:
                    quinzaine = int(val)
                    break

        if "Semaine" in text and hebdomadaire is None:
            for td in tds:
                val = parse_montant(td.get_text())
                if val > 100:
                    hebdomadaire = int(val)
                    break

        if "Jour" in text and journalier is None:
            for td in tds:
                val = parse_montant(td.get_text())
                if val > 50:
                    journalier = int(val)
                    break

        if "Heure" in text and horaire is None:
            for td in tds:
                val = parse_montant(td.get_text())
                if 5 < val < 200:
                    horaire = int(val)
                    break

        if annuel is not None and mensuel is not None and journalier is not None:
            break

    if not annuel:
        raise ValueError("Impossible d'extraire le plafond annuel SS")

    if horaire is None and mensuel is not None:
        horaire = int(round(float(mensuel) / 151.67))
    if horaire is None and journalier is not None:
        horaire = int(round(float(journalier) / 7))

    return {
        "annuel": annuel,
        "trimestriel": trimestriel,
        "mensuel": mensuel,
        "quinzaine": quinzaine,
        "hebdomadaire": hebdomadaire,
        "journalier": journalier,
        "horaire": horaire,
        "annee": annee,
    }


# --- SCRAPER ---


def get_plafonds_ss() -> dict | None:
    """
    Scrape le site de l'URSSAF pour récupérer l'ensemble des plafonds de la SS.
    """
    try:
        print(f"Scraping de l'URL : {URL_URSSAF}...", file=sys.stderr)
        session = get_session()
        r = session.get(URL_URSSAF, timeout=20)
        r.raise_for_status()

        soup = BeautifulSoup(r.text, "html.parser")
        plafonds = extract_pss_data(soup)

        for k, v in plafonds.items():
            if v is not None:
                print(f"  - Plafond '{k}' : {v}", file=sys.stderr)

        return plafonds

    except Exception as e:
        print(f"ERREUR : Le scraping a échoué. Raison : {e}", file=sys.stderr)
        return None


# --- FONCTION PRINCIPALE ---


def main():
    """Orchestre le scraping et génère la sortie JSON pour l'orchestrateur."""
    plafonds_data = get_plafonds_ss()

    if not plafonds_data:
        print(
            "ERREUR CRITIQUE: Le scraping des plafonds de la SS a échoué ou n'a retourné aucune donnée.",
            file=sys.stderr,
        )
        sys.exit(1)

    payload = {
        "id": "plafonds_securite_sociale",
        "type": "bareme_plafond",
        "libelle": "Plafonds de la Sécurité Sociale",
        "sections": plafonds_data,
        "data": plafonds_data,
        "meta": {
            "source": [
                {
                    "url": URL_URSSAF,
                    "label": "URSSAF - Plafonds de la Sécurité Sociale",
                    "date_doc": "",
                }
            ],
            "scraped_at": iso_now(),
            "generator": "scripts/PSS/PSS.py",
            "method": "primary",
        },
    }

    # Impression du JSON final sur la sortie standard
    print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
