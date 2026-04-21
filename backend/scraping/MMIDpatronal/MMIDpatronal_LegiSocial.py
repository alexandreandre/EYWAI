# scripts/MMIDpatronal/MMIDpatronal_LegiSocial.py
import json
import re
from datetime import datetime, timezone

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


def iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_taux(text: str) -> float | None:
    if not text:
        return None
    try:
        cleaned_text = text.replace(",", ".").replace("%", "").strip()
        m = re.search(r"([0-9]+\.?[0-9]*)", cleaned_text)
        if not m:
            return None
        return round(float(m.group(1)) / 100.0, 5)
    except Exception:
        return None


def get_taux_maladie_legisocial() -> tuple[dict | None, str]:
    resolved_url = ""
    try:
        r = fetch_legisocial(URL_LEGISOCIAL_TEMPLATE)
        resolved_url = r.url
        soup = BeautifulSoup(r.text, "html.parser")

        page_year = datetime.now().year
        m_year = re.search(r"-(\d{4})\.html", resolved_url)
        if m_year:
            page_year = int(m_year.group(1))
        title_needle = f"Quels sont les taux de cotisations en {page_year}"

        table_title = soup.find(
            lambda tag: (
                tag.name in ["h2", "h3"] and title_needle in tag.get_text()
            )
        )
        if not table_title:
            raise ValueError(f"Titre de la table {page_year} introuvable.")
        table = table_title.find_next("table")
        if not table:
            raise ValueError("Table des cotisations introuvable.")

        taux_trouves: dict[str, float] = {}
        for row in table.find("tbody").find_all("tr"):
            cells = row.find_all("td")
            if len(cells) > 4:
                libelle = cells[0].get_text().lower()
                if "maladie" in libelle and "alsace-moselle" not in libelle:
                    taux_text = cells[4].get_text()
                    taux = parse_taux(taux_text)
                    if taux is None:
                        continue
                    if "≤" in libelle or "<" in libelle:
                        taux_trouves["reduit"] = taux
                    elif ">" in libelle:
                        taux_trouves["plein"] = taux

        if "reduit" in taux_trouves or "plein" in taux_trouves:
            return taux_trouves, resolved_url
        return None, resolved_url
    except Exception:
        return None, resolved_url


def build_payload(
    rate_plein: float | None, rate_reduit: float | None, source_url: str
) -> dict:
    return {
        "id": "securite_sociale_maladie",
        "type": "cotisation",
        "libelle": "Sécurité sociale - Maladie, Maternité, Invalidité, Décès",
        "base": "brut",
        "valeurs": {
            "salarial": None,
            "patronal_plein": rate_plein,
            "patronal_reduit": rate_reduit,
        },
        "meta": {
            "source": [
                {
                    "url": source_url,
                    "label": "LégiSocial — Taux cotisations URSSAF 2025",
                    "date_doc": "",
                }
            ],
            "scraped_at": iso_now(),
            "generator": "scripts/MMIDpatronal/MMIDpatronal_LegiSocial.py",
            "method": "secondary",
        },
    }


def main() -> None:
    rates, source_url = get_taux_maladie_legisocial()
    rates = rates or {}
    payload = build_payload(
        rates.get("plein"),
        rates.get("reduit"),
        source_url or URL_LEGISOCIAL_TEMPLATE.format(year=datetime.now().year),
    )
    print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
