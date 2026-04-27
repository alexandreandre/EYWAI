# scripts/IJmaladie/IJmaladie_LegiSocial.py
import json
import re
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

URL_LEGISOCIAL_TEMPLATE = (
    "https://www.legisocial.fr/reperes-sociaux/indemnites-journalieres-de-securite-sociale-ijss-{year}.html"
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


def parse_valeur_numerique(text: str) -> float:
    if not text:
        return 0.0
    cleaned = (
        text.replace("€", "")
        .replace("\xa0", "")
        .replace("\u202f", "")
        .replace(" ", "")
        .replace(",", ".")
    )
    m = re.search(r"([0-9]+\.?[0-9]*)", cleaned)
    return float(m.group(1)) if m else 0.0


def get_all_plafonds_ij_legisocial() -> tuple[dict | None, str]:
    resolved_url = ""
    try:
        r = fetch_legisocial(URL_LEGISOCIAL_TEMPLATE)
        resolved_url = r.url
        soup = BeautifulSoup(r.text, "html.parser")

        plafonds: dict = {}
        maladie_hits = 0

        for header in soup.find_all("h3"):
            header_text = header.get_text().lower()
            table = header.find_next("table")
            if not table:
                continue

            # Maladie: 2e valeur <mark>
            if "arrêt de travail maladie" in header_text:
                valeur_cell = table.find("mark")
                if valeur_cell:
                    valeur_maladie = parse_valeur_numerique(valeur_cell.get_text())
                    maladie_hits += 1
                    if maladie_hits == 2 and "maladie" not in plafonds:
                        plafonds["maladie"] = valeur_maladie

            # Maternité/Paternité: 1re valeur "pour tous les assurés"
            elif (
                "congé de maternité" in header_text
                and "maternite_paternite" not in plafonds
            ):
                row = table.find(
                    lambda tag: (
                        tag.name == "td"
                        and "pour tous les assurés" in tag.get_text(strip=True).lower()
                    )
                )
                if row:
                    parent_row = row.find_parent("tr")
                    cells = parent_row.find_all("td")
                    if len(cells) >= 2:
                        valeur = parse_valeur_numerique(cells[1].get_text())
                        plafonds["maternite_paternite"] = valeur

            # AT/MP: 1re occurrence jusqu'au 28e, puis à partir du 29e
            elif "accident du travail" in header_text:
                tbody = table.find("tbody") or table
                for row in tbody.find_all("tr"):
                    libelle = row.get_text().lower()
                    cells = row.find_all("td")
                    valeur_cell = next((c for c in cells if "€" in c.get_text()), None)
                    if not valeur_cell:
                        continue
                    valeur = parse_valeur_numerique(valeur_cell.get_text())

                    if "jusqu'au 28" in libelle and "at_mp" not in plafonds:
                        plafonds["at_mp"] = valeur
                    elif "partir du 29" in libelle and "at_mp_majoree" not in plafonds:
                        plafonds["at_mp_majoree"] = valeur

        if set(plafonds.keys()) != {
            "maladie",
            "maternite_paternite",
            "at_mp",
            "at_mp_majoree",
        }:
            raise ValueError(f"Incomplet: {plafonds}")

        return plafonds, resolved_url
    except Exception:
        return None, resolved_url


def build_payload(vals: dict | None, source_url: str) -> dict:
    valeurs = {
        "maladie": None,
        "maternite_paternite": None,
        "at_mp": None,
        "at_mp_majoree": None,
        "unite": "EUR/jour",
    }
    if vals:
        valeurs.update(
            {
                "maladie": vals.get("maladie"),
                "maternite_paternite": vals.get("maternite_paternite"),
                "at_mp": vals.get("at_mp"),
                "at_mp_majoree": vals.get("at_mp_majoree"),
            }
        )
    return {
        "id": "ij_maladie",
        "type": "secu",
        "libelle": "Indemnités journalières — montants maximums",
        "base": None,
        "valeurs": valeurs,
        "meta": {
            "source": [
                {
                    "url": source_url,
                    "label": "LégiSocial — IJSS 2025",
                    "date_doc": "",
                }
            ],
            "scraped_at": iso_now(),
            "generator": "scripts/IJmaladie/IJmaladie_LegiSocial.py",
            "method": "secondary",
        },
    }


def main() -> None:
    vals, source_url = get_all_plafonds_ij_legisocial()
    payload = build_payload(vals, source_url)
    print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
