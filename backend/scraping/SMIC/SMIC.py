# scripts/SMIC/SMIC.py

import json
import re
import sys
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

URL_URSSAF = (
    "https://www.urssaf.fr/accueil/outils-documentation/taux-baremes/montant-smic.html"
)


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
    """Convertit '1 823,03 €' ou '1\xa0823,03 €' en 1823.03"""
    import re
    # Normalise : supprime espaces normaux, insécables,
    # apostrophes, points de milliers
    cleaned = (texte
               .replace('\xa0', '')
               .replace('\u202f', '')
               .replace(' ', '')
               .replace('\u2009', '')
               .strip())
    # Remplace virgule décimale par point
    cleaned = cleaned.replace(',', '.')
    # Extrait le premier nombre décimal ou entier
    match = re.search(r'\d+\.?\d*', cleaned)
    if match:
        return float(match.group())
    return 0.0


def extract_smic_data(soup: BeautifulSoup) -> dict:
    """
    Extrait les données SMIC depuis les tableaux URSSAF.
    Parcourt tous les tr : chaque ligne « Smic horaire brut »
    ajoute une valeur (> 5 €) dans l'ordre (cas général, 17–18 ans, etc.).
    """
    rows = soup.find_all("tr")

    horaires: list[float] = []
    smic_mensuel_brut = None
    annee = datetime.now().year

    for tr in rows:
        text = tr.get_text(strip=True, separator=" | ")

        if "Smic horaire brut" in text:
            tds = tr.find_all(["td", "th"])
            for td in tds:
                val = parse_montant(td.get_text())
                if val > 5:
                    horaires.append(val)
                    break

        if "mensuel" in text.lower() and smic_mensuel_brut is None:
            tds = tr.find_all(["td", "th"])
            for td in tds:
                val = parse_montant(td.get_text())
                if val > 1000:
                    smic_mensuel_brut = val
                    break

        if "janvier" in text.lower():
            m = re.search(r"20\d{2}", text)
            if m:
                annee = int(m.group())

    if not horaires:
        raise ValueError("Impossible d'extraire le SMIC horaire brut")

    smic_horaire_brut = horaires[0]
    if smic_mensuel_brut is None:
        smic_mensuel_brut = round(smic_horaire_brut * 35 * 52 / 12, 2)

    cas_general = horaires[0]
    jeune_17 = horaires[1] if len(horaires) > 1 else horaires[0]
    jeune_moins_17 = horaires[2] if len(horaires) > 2 else horaires[0]

    return {
        "smic_horaire_brut": smic_horaire_brut,
        "smic_mensuel_brut": smic_mensuel_brut,
        "annee": annee,
        "source": "URSSAF",
        "cas_general": cas_general,
        "jeune_17_ans": jeune_17,
        "jeune_moins_17_ans": jeune_moins_17,
    }


def get_tous_les_smic() -> dict | None:
    """Scrape l'URSSAF et retourne le dict sections (taux horaires + agrégats)."""
    try:
        print(f"Scraping de l'URL : {URL_URSSAF}...", file=sys.stderr)
        session = get_session()
        r = session.get(URL_URSSAF, timeout=20)
        r.raise_for_status()

        soup = BeautifulSoup(r.text, "html.parser")
        data = extract_smic_data(soup)

        print(
            f"  - SMIC horaire brut (réf.): {data['smic_horaire_brut']} € | "
            f"mensuel: {data['smic_mensuel_brut']} € | année: {data['annee']}",
            file=sys.stderr,
        )
        print(
            f"  - Par cas: général={data['cas_general']}, "
            f"17–18={data['jeune_17_ans']}, <17={data['jeune_moins_17_ans']}",
            file=sys.stderr,
        )

        # Pour l'orchestrateur : comparer uniquement des nombres (pas la clé str "source")
        sections = {k: v for k, v in data.items() if k != "source"}
        return sections

    except Exception as e:
        print(f"ERREUR : Le scraping a échoué. Raison : {e}", file=sys.stderr)
        return None


def main():
    """Orchestre le scraping et génère la sortie JSON pour l'orchestrateur."""
    smic_data = get_tous_les_smic()

    if not smic_data:
        print(
            "ERREUR CRITIQUE: Le scraping du SMIC a échoué ou n'a retourné aucune donnée.",
            file=sys.stderr,
        )
        sys.exit(1)

    payload = {
        "id": "smic_horaire",
        "type": "bareme_horaire",
        "libelle": "Salaire Minimum Interprofessionnel de Croissance (SMIC) - Taux horaire",
        "sections": smic_data,
        "meta": {
            "source": [
                {"url": URL_URSSAF, "label": "URSSAF - Montant du Smic", "date_doc": ""}
            ],
            "scraped_at": iso_now(),
            "generator": "scripts/SMIC/SMIC.py",
            "method": "primary",
        },
    }

    print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
