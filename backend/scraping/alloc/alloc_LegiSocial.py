# scripts/alloc/alloc_LegiSocial.py

import json
import re
import sys
from datetime import datetime

import requests
from bs4 import BeautifulSoup

URL_LEGISOCIAL_TEMPLATE = (
    "https://www.legisocial.fr/reperes-sociaux/taux-cotisations-sociales-urssaf-{year}.html"
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


def parse_taux(text: str) -> float | None:
    """
    Nettoie un texte (ex: "3,45 %"), le convertit en float (3.45)
    puis en taux réel (0.0345).
    """
    if not text:
        return None
    try:
        cleaned_text = text.replace(",", ".").replace("%", "").strip()
        numeric_part = re.search(r"([0-9]+\.?[0-9]*)", cleaned_text)
        if not numeric_part:
            return None
        taux = float(numeric_part.group(1)) / 100.0
        return round(taux, 5)
    except (ValueError, AttributeError):
        return None


def make_payload(plein, reduit, source_url: str):
    return {
        "id": "allocations_familiales",
        "type": "cotisation",
        "libelle": "Allocations familiales",
        "base": "brut",
        "valeurs": {
            "salarial": None,
            "patronal_plein": plein,
            "patronal_reduit": reduit,
        },
        "meta": {
            "source": [{"url": source_url, "label": "LegiSocial", "date_doc": ""}],
            "generator": "scripts/alloc/alloc_LegiSocial.py",
        },
    }


def get_taux_alloc_legisocial() -> tuple[dict | None, str]:
    """
    Scrape LegiSocial pour trouver les taux plein et réduit.
    STRATÉGIE IDENTIQUE :
      1) Trouver le titre contenant 'Quels sont les taux'
      2) Prendre la table qui suit
      3) Dans les lignes 'allocations familiales', lire la 5ᵉ cellule (index 4)
      4) Classer réduit si '≤' ou '<' dans le libellé ; plein si '>' dans le libellé
    """
    response = fetch_legisocial(URL_LEGISOCIAL_TEMPLATE)
    resolved_url = response.url

    soup = BeautifulSoup(response.text, "html.parser")

    page_year = datetime.now().year
    m_year = re.search(r"-(\d{4})\.html", resolved_url)
    if m_year:
        page_year = int(m_year.group(1))

    # 1) Trouver la table principale des cotisations
    # Recherche flexible : plusieurs variantes possibles du titre
    table_title = None
    possible_titles = [
        f"Quels sont les taux de cotisations en {page_year}",
        "Quels sont les taux de cotisations",
        "Quels sont les taux",
        "taux de cotisations",
    ]

    for title_text in possible_titles:
        table_title = soup.find(
            lambda tag: (
                tag.name in ["h2", "h3"]
                and title_text.lower() in tag.get_text().lower()
            )
        )
        if table_title:
            break

    # Si aucun titre trouvé, chercher directement les tableaux avec "allocations familiales"
    if not table_title:
        # Fallback : chercher directement un tableau contenant "allocations familiales"
        for table in soup.find_all("table"):
            table_text = table.get_text().lower()
            if "allocations familiales" in table_text:
                table_title = table.find_previous(["h2", "h3", "h4", "h5"])
                if table_title:
                    break

    if not table_title:
        raise ValueError("Titre de la table principale des cotisations introuvable.")

    # Si on a trouvé un titre, chercher la table qui suit
    # Sinon, utiliser la table qu'on a déjà trouvée dans le fallback
    if table_title.name in ["h2", "h3", "h4", "h5"]:
        table = table_title.find_next("table")
        if not table:
            raise ValueError("Table des cotisations introuvable après le titre.")
    else:
        # Dans le fallback, table_title est en fait la table elle-même
        table = table_title
        table_title = None  # Réinitialiser pour éviter la confusion

    # 2) Parcourir les lignes pour trouver les deux taux
    taux_trouves = {}
    tbody = table.find("tbody") or table
    for row in tbody.find_all("tr"):
        cells = row.find_all("td")
        if len(cells) > 4:
            libelle = cells[0].get_text().lower()
            if "allocations familiales" in libelle:
                taux_text = cells[4].get_text()
                taux = parse_taux(taux_text)

                if taux is not None:
                    # 3) Classification identique : signes dans le libellé
                    if "≤" in libelle or "<" in libelle:
                        # print(f"Taux Allocations Familiales (réduit) trouvé : {taux*100:.2f}%")
                        taux_trouves["reduit"] = taux
                    elif ">" in libelle:
                        # print(f"Taux Allocations Familiales (plein) trouvé : {taux*100:.2f}%")
                        taux_trouves["plein"] = taux

    if "reduit" in taux_trouves and "plein" in taux_trouves:
        return taux_trouves, resolved_url
    else:
        raise ValueError(
            "Impossible de trouver les deux taux (réduit et plein) pour les allocations familiales."
        )


if __name__ == "__main__":
    try:
        tous_les_taux, source_url = get_taux_alloc_legisocial()
        payload = make_payload(
            tous_les_taux.get("plein"),
            tous_les_taux.get("reduit"),
            source_url,
        )
        print(json.dumps(payload, ensure_ascii=False))
        # succès si les deux valeurs sont présentes
        sys.exit(
            0
            if (
                payload["valeurs"]["patronal_plein"] is not None
                and payload["valeurs"]["patronal_reduit"] is not None
            )
            else 2
        )
    except Exception as e:
        y = datetime.now().year
        print(
            json.dumps(
                make_payload(
                    None,
                    None,
                    URL_LEGISOCIAL_TEMPLATE.format(year=y),
                ),
                ensure_ascii=False,
            )
        )
        print(f"ERREUR : {e}", file=sys.stderr)
        sys.exit(2)
