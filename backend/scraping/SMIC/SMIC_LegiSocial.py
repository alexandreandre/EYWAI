# scripts/SMIC/SMIC_LegiSocial.py

import json
import re
import sys
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

URL_LEGISOCIAL_TEMPLATE = (
    "https://www.legisocial.fr/reperes-sociaux/calcul-salaire-smic-{year}.html"
)


def fetch_legisocial(url_template: str) -> requests.Response:
    year = datetime.now().year
    for y in [year, year - 1]:
        url = url_template.format(year=y)
        try:
            resp = requests.get(
                url, timeout=15, headers={"User-Agent": "Mozilla/5.0"}
            )
            if resp.status_code == 200:
                return resp
        except requests.RequestException:
            continue
    raise RuntimeError(
        f"URL LegiSocial inaccessible pour {year} et {year - 1}"
    )


# --- UTILITAIRES ---
def iso_now() -> str:
    """Retourne la date et l'heure actuelles au format ISO 8601 UTC."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_valeur_numerique(text: str) -> float:
    """Nettoie et convertit un texte en nombre (float)."""
    if not text:
        return 0.0
    cleaned = (
        text.replace("€", "").replace("\xa0", "").replace(" ", "").replace(",", ".")
    )
    match = re.search(r"([0-9]+\.?[0-9]*)", cleaned)
    return float(match.group(1)) if match else 0.0


# --- SCRAPER ---
def get_smic_legisocial() -> tuple[dict | None, str]:
    """
    Scrape le site LegiSocial pour trouver la valeur du SMIC horaire.
    NOTE: Cette source ne détaille que le cas général.
    """
    resolved_url = ""
    try:
        response = fetch_legisocial(URL_LEGISOCIAL_TEMPLATE)
        resolved_url = response.url
        print(f"Scraping de l'URL : {resolved_url}...", file=sys.stderr)
        soup = BeautifulSoup(response.text, "html.parser")

        page_text = soup.get_text(" ", strip=True)

        motif = re.search(
            r"smic horaire est fixé à ([0-9,]+)\s*euros brut dans le cas général",
            page_text,
            re.IGNORECASE,
        )

        if not motif:
            raise ValueError(
                "Impossible de trouver la phrase contenant la valeur du SMIC sur la page."
            )

        smic_general_str = motif.group(1)
        smic_general = parse_valeur_numerique(smic_general_str)

        print(
            f"  - SMIC horaire (cas général) trouvé : {smic_general} €", file=sys.stderr
        )

        # Ce scraper ne retourne que le cas général car la source est limitée
        return {"cas_general": smic_general}, resolved_url

    except Exception as e:
        print(f"ERREUR : Le scraping a échoué. Raison : {e}", file=sys.stderr)
        return None, resolved_url


# --- FONCTION PRINCIPALE ---
def main():
    """Orchestre le scraping et génère la sortie JSON pour l'orchestrateur."""
    smic_data, resolved_url = get_smic_legisocial()

    if not smic_data:
        print(
            "ERREUR CRITIQUE: Le scraping du SMIC via LegiSocial a échoué.",
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
                {
                    "url": resolved_url
                    or URL_LEGISOCIAL_TEMPLATE.format(year=datetime.now().year),
                    "label": "LegiSocial - Calcul du SMIC",
                    "date_doc": "",
                }
            ],
            "scraped_at": iso_now(),
            "generator": "scripts/SMIC/SMIC_LegiSocial.py",
            "method": "secondary",
        },
    }

    # Impression du JSON final sur la sortie standard
    print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
