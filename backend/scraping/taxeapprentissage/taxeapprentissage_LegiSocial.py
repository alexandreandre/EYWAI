# scripts/taxeapprentissage/taxeapprentissage_LegiSocial.py

import json
import re
import sys
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

URL_LEGISOCIAL_TEMPLATE = (
    "https://www.legisocial.fr/reperes-sociaux/taxe-apprentissage-{year}.html"
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


def parse_taux(text: str) -> float | None:
    """Nettoie un texte (ex: "0,68 %") et le convertit en taux réel (0.0068)."""
    if not text:
        return None
    try:
        cleaned_text = text.replace(",", ".").replace("%", "").strip()
        numeric_part = re.search(r"([0-9]+\.?[0-9]*)", cleaned_text)
        if not numeric_part:
            return None
        taux = float(numeric_part.group(1)) / 100.0
        return round(taux, 6)
    except (ValueError, AttributeError):
        return None


# --- SCRAPER ---
def scrape_taxe_apprentissage_legisocial() -> tuple[dict | None, str]:
    """
    Scrape les taux totaux de la taxe d'apprentissage depuis LegiSocial.
    """
    resolved_url = ""
    try:
        r = fetch_legisocial(URL_LEGISOCIAL_TEMPLATE)
        resolved_url = r.url
        print(f"Scraping de l'URL : {resolved_url}...", file=sys.stderr)
        soup = BeautifulSoup(r.text, "html.parser")

        # --- LOGIQUE DE CIBLAGE SIMPLE ET ROBUSTE ---
        target_row = None
        # On parcourt toutes les lignes de la page
        for row in soup.find_all("tr"):
            first_cell = row.find("td")
            # Si la première cellule contient "Taux", c'est la bonne ligne
            if first_cell and "Taux" in first_cell.get_text(strip=True):
                target_row = row
                break

        if not target_row:
            raise ValueError(
                "Impossible de trouver la ligne du tableau contenant les taux."
            )

        cells = target_row.find_all("td")
        if len(cells) < 2:
            raise ValueError("La ligne des taux ne contient pas assez de cellules.")

        rates_cell = cells[1]  # La deuxième cellule contient les valeurs
        list_items = rates_cell.find("ul").find_all("li")
        if len(list_items) < 2:
            raise ValueError(
                "La liste des taux ne contient pas les deux valeurs attendues."
            )

        taux_metropole = parse_taux(list_items[0].get_text())
        taux_alsace_moselle = parse_taux(list_items[1].get_text())

        if taux_metropole is None or taux_alsace_moselle is None:
            raise ValueError("Un ou plusieurs taux n'ont pas pu être extraits.")

        print(
            f"  - Taux total (Métropole) trouvé : {taux_metropole * 100:.2f}%",
            file=sys.stderr,
        )
        print(
            f"  - Taux total (Alsace-Moselle) trouvé : {taux_alsace_moselle * 100:.2f}%",
            file=sys.stderr,
        )

        return {
            "total": {
                "taux_metropole": taux_metropole,
                "taux_alsace_moselle": taux_alsace_moselle,
            }
        }, resolved_url

    except Exception as e:
        print(f"ERREUR : Le scraping a échoué. Raison : {e}", file=sys.stderr)
        return None, resolved_url


# --- FONCTION PRINCIPALE ---
def main():
    """Orchestre le scraping et génère la sortie JSON pour l'orchestrateur."""
    rates_data, resolved_url = scrape_taxe_apprentissage_legisocial()

    if not rates_data:
        print(
            "ERREUR CRITIQUE: Le scraping de la taxe d'apprentissage via LegiSocial a échoué.",
            file=sys.stderr,
        )
        sys.exit(1)

    payload = {
        "id": "taxe_apprentissage",
        "type": "cotisation",
        "libelle": "Taxe d'Apprentissage",
        "sections": {"salarial": None, "total": rates_data.get("total")},
        "meta": {
            "source": [
                {
                    "url": resolved_url
                    or URL_LEGISOCIAL_TEMPLATE.format(year=datetime.now().year),
                    "label": "LegiSocial - Taxe d'apprentissage",
                    "date_doc": "",
                }
            ],
            "scraped_at": iso_now(),
            "generator": "scripts/taxeapprentissage/taxeapprentissage_LegiSocial.py",
            "method": "secondary",
        },
    }

    print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
