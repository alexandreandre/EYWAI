# scripts/CFP/CFP_LegiSocial.py

import json
import re
import sys
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

URL_LEGISOCIAL_TEMPLATE = (
    "https://www.legisocial.fr/reperes-sociaux/taxe-formation-professionnelle-continue-{year}.html"
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
    """Nettoie un texte (ex: "0,55%") et le convertit en taux réel (0.0055)."""
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
def scrape_cfp_rates_legisocial() -> tuple[dict | None, str]:
    """
    Scrape le site de LegiSocial pour les taux de la Contribution à la Formation Professionnelle (CFP).
    """
    resolved_url = ""
    try:
        r = fetch_legisocial(URL_LEGISOCIAL_TEMPLATE)
        resolved_url = r.url
        print(f"Scraping de l'URL : {resolved_url}...", file=sys.stderr)

        soup = BeautifulSoup(r.text, "html.parser")

        taux_moins_11 = None
        taux_11_et_plus = None

        # --- NOUVELLE LOGIQUE DE CIBLAGE PLUS SOUPLE ---
        # 1. On cherche une balise qui contient le texte "Effectif" pour trouver le tableau
        header_tag = soup.find(
            lambda tag: (
                tag.name in ["p", "td", "th"] and "Effectif" in tag.get_text(strip=True)
            )
        )
        if not header_tag:
            raise ValueError(
                "Impossible de trouver l'en-tête de la table des taux ('Effectif')."
            )

        # 2. On remonte jusqu'à la balise <table> parente
        table = header_tag.find_parent("table")
        if not table:
            raise ValueError(
                "Impossible de trouver la balise <table> parente de l'en-tête."
            )

        # 3. Parcourir les lignes du tableau (libellés LegiSocial variables)
        for row in table.find_all("tr"):
            cells = row.find_all("td")
            if len(cells) < 2:
                continue
            label = cells[0].get_text(" ", strip=True).lower()
            valeur_text = cells[1].get_text(strip=True)
            taux = parse_taux(valeur_text)
            if taux is None:
                continue
            if any(
                k in label
                for k in (
                    "< 11",
                    "moins de 11",
                    "inférieur à 11",
                    "inferieur a 11",
                    "strictement inférieur",
                )
            ):
                taux_moins_11 = taux
            elif any(
                k in label
                for k in (
                    "≥ 11",
                    ">= 11",
                    "11 et plus",
                    "11 salariés et plus",
                    "11 salaries et plus",
                    "égal ou supérieur",
                    "egal ou superieur",
                )
            ):
                taux_11_et_plus = taux

        if taux_moins_11 is None or taux_11_et_plus is None:
            # Repli : deux plus petits taux % trouvés dans le tableau
            found: list[float] = []
            for row in table.find_all("tr"):
                cells = row.find_all("td")
                if len(cells) >= 2:
                    t = parse_taux(cells[1].get_text(strip=True))
                    if t is not None and 0 < t < 0.02:
                        found.append(t)
            if len(found) >= 2:
                unique = sorted(set(found))
                taux_moins_11 = taux_moins_11 or unique[0]
                taux_11_et_plus = taux_11_et_plus or unique[-1]

        if taux_moins_11 is None or taux_11_et_plus is None:
            raise ValueError("Impossible de trouver les deux taux CFP sur la page.")

        print(
            f"  - Taux (< 11 salariés) trouvé : {taux_moins_11 * 100:.2f}%",
            file=sys.stderr,
        )
        print(
            f"  - Taux (11+ salariés) trouvé : {taux_11_et_plus * 100:.2f}%",
            file=sys.stderr,
        )

        return {
            "patronal_moins_11": taux_moins_11,
            "patronal_11_et_plus": taux_11_et_plus,
        }, resolved_url

    except Exception as e:
        print(f"ERREUR : Le scraping a échoué. Raison : {e}", file=sys.stderr)
        return None, resolved_url


# --- FONCTION PRINCIPALE ---
def main():
    """Orchestre le scraping et génère la sortie JSON pour l'orchestrateur."""
    rates_data, resolved_url = scrape_cfp_rates_legisocial()

    if not rates_data:
        print(
            "ERREUR CRITIQUE: Le scraping des taux de CFP via LegiSocial a échoué.",
            file=sys.stderr,
        )
        sys.exit(1)

    payload = {
        "id": "cfp",
        "type": "cotisation",
        "libelle": "Contribution à la Formation Professionnelle (CFP)",
        "sections": {
            "salarial": None,
            "patronal_moins_11": rates_data.get("patronal_moins_11"),
            "patronal_11_et_plus": rates_data.get("patronal_11_et_plus"),
        },
        "meta": {
            "source": [
                {
                    "url": resolved_url
                    or URL_LEGISOCIAL_TEMPLATE.format(year=datetime.now().year),
                    "label": "LegiSocial - Taxe Formation Professionnelle",
                    "date_doc": "",
                }
            ],
            "scraped_at": iso_now(),
            "generator": "scripts/CFP/CFP_LegiSocial.py",
            "method": "secondary",
        },
    }

    print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
