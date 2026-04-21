# scripts/PSS/PSS_LegiSocial.py

import json
import sys
import time
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager

URL_LEGISOCIAL_TEMPLATE = (
    "https://www.legisocial.fr/reperes-sociaux/plafond-securite-sociale-{year}.html"
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


def parse_valeur_numerique(text: str) -> int:
    """Nettoie un texte (ex: "47.100 €"), le convertit en entier."""
    if not text:
        return 0
    cleaned_text = (
        text.replace(".", "")
        .replace("€", "")
        .replace("\xa0", "")
        .replace(" ", "")
        .strip()
    )
    return int(cleaned_text)


def find_plafond_table(soup: BeautifulSoup):
    """
    Stratégies multi-sélecteurs (ordre) :
    a) table dont un th contient « plafond » (insensible à la casse)
    b) premier tableau avec au moins 2 cellules numériques « montant » sur une ligne
    c) table dont le texte contient « annuel »
    d) premier tableau présent (repli)
    """
    for table in soup.find_all("table"):
        headers = [
            th.get_text(strip=True).lower() for th in table.find_all("th")
        ]
        if any("plafond" in h for h in headers):
            return table

    for table in soup.find_all("table"):
        for tr in table.find_all("tr"):
            cells = tr.find_all(["td", "th"])
            numeric_count = 0
            for c in cells:
                try:
                    v = parse_valeur_numerique(c.get_text())
                    if v >= 100:
                        numeric_count += 1
                except (ValueError, TypeError):
                    continue
            if numeric_count >= 2:
                return table

    for table in soup.find_all("table"):
        if "annuel" in table.get_text().lower():
            return table

    tables = soup.find_all("table")
    return tables[0] if tables else None


def extract_plafonds_from_soup(soup: BeautifulSoup) -> dict:
    """Extrait les plafonds SS depuis une soupe HTML déjà chargée."""
    table = find_plafond_table(soup)
    if not table:
        raise ValueError("Table des plafonds introuvable sur la page.")

    plafonds: dict = {}
    key_mapping = {
        "annuel": "annuel",
        "trimestriel": "trimestriel",
        "mensuel": "mensuel",
        "jour": "journalier",
        "heure": "horaire",
    }

    for row in table.find_all("tr"):
        label_cell = row.find(["th", "td"])
        if not label_cell:
            continue

        libelle = label_cell.get_text().lower()
        value_cell = label_cell.find_next_sibling(["th", "td"])

        if value_cell:
            for keyword, key in key_mapping.items():
                if keyword in libelle:
                    valeur = parse_valeur_numerique(value_cell.get_text())
                    plafonds[key] = valeur
                    print(
                        f"  - Plafond '{key}' trouvé : {valeur} €", file=sys.stderr
                    )
                    break

    if len(plafonds) < 5:
        raise ValueError(
            f"Tous les plafonds principaux n'ont pas été trouvés. Requis: 5, Trouvés: {len(plafonds)}"
        )

    return plafonds


def _scrape_with_selenium(target_url: str) -> str:
    """Retourne le HTML de la page via Selenium (headless)."""
    print(
        "Initialisation du navigateur Selenium en mode invisible...",
        file=sys.stderr,
    )
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36"
    )

    driver = webdriver.Chrome(
        service=ChromeService(ChromeDriverManager().install()),
        options=options,
    )
    try:
        driver.set_page_load_timeout(30)
        driver.implicitly_wait(10)
        print(f"Navigation vers l'URL : {target_url}...", file=sys.stderr)
        driver.get(target_url)
        time.sleep(3)
        print("Récupération du code HTML final...", file=sys.stderr)
        return driver.page_source
    finally:
        print("Fermeture du navigateur Selenium.", file=sys.stderr)
        driver.quit()


def get_plafonds_ss_legisocial() -> tuple[dict | None, str]:
    """
    Scrape LegiSocial : Selenium en priorité, repli requests + BeautifulSoup
    sur la même URL si Selenium échoue.
    """
    r = fetch_legisocial(URL_LEGISOCIAL_TEMPLATE)
    target_url = r.url

    try:
        page_html = _scrape_with_selenium(target_url)
        soup = BeautifulSoup(page_html, "html.parser")
        plafonds = extract_plafonds_from_soup(soup)
        return plafonds, target_url
    except (WebDriverException, Exception) as e:
        print(
            f"[PSS LegiSocial] Selenium indisponible ou erreur ({e!r}) ; "
            "fallback requests + BeautifulSoup.",
            file=sys.stderr,
        )
        try:
            soup = BeautifulSoup(r.text, "html.parser")
            plafonds = extract_plafonds_from_soup(soup)
            return plafonds, target_url
        except Exception as e2:
            print(
                f"ERREUR : Le scraping (fallback) a échoué. Raison : {e2}",
                file=sys.stderr,
            )
            return None, target_url


# --- FONCTION PRINCIPALE ---
def main():
    """Orchestre le scraping et génère la sortie JSON pour l'orchestrateur."""
    plafonds_data, source_url = get_plafonds_ss_legisocial()
    if not source_url:
        source_url = URL_LEGISOCIAL_TEMPLATE.format(year=datetime.now().year)

    if not plafonds_data:
        print(
            "ERREUR CRITIQUE: Le scraping des plafonds via LegiSocial a échoué.",
            file=sys.stderr,
        )
        sys.exit(1)

    payload = {
        "id": "plafonds_securite_sociale",
        "type": "bareme_plafond",
        "libelle": "Plafonds de la Sécurité Sociale",
        "sections": plafonds_data,
        "meta": {
            "source": [
                {
                    "url": source_url,
                    "label": "LegiSocial - Plafond de la Sécurité Sociale",
                    "date_doc": "",
                }
            ],
            "scraped_at": iso_now(),
            "generator": "scripts/PSS/PSS_LegiSocial.py",
            "method": "secondary",
        },
    }

    # Impression du JSON final sur la sortie standard
    print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
