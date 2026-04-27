# scripts/CSG/CSG_LegiSocial.py

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
    m = re.search(r"([0-9]+(?:[.,][0-9]+)?)\s*%", text)
    if not m:
        return None
    try:
        return round(float(m.group(1).replace(",", ".")) / 100.0, 6)
    except Exception:
        return None


def fetch_page() -> tuple[BeautifulSoup, str]:
    r = fetch_legisocial(URL_LEGISOCIAL_TEMPLATE)
    return BeautifulSoup(r.text, "html.parser"), r.url


def get_taux_csg_legisocial() -> tuple[dict | None, str]:
    """
    Retourne {"deductible": float, "non_deductible": float} ou None.
    deductible = CSG déductible
    non_deductible = CSG non déductible + CRDS non déductible
    """
    soup, source_url = fetch_page()

    # Trouver le bloc "COTISATIONS CSG et CRDS"
    target_h3 = None
    for h3 in soup.find_all("h3"):
        if (
            "csg" in h3.get_text(strip=True).lower()
            and "crds" in h3.get_text(strip=True).lower()
        ):
            target_h3 = h3
            break
    if not target_h3:
        return None, source_url

    table = target_h3.find_next("table")
    if not table:
        return None, source_url

    # Parcours du tbody, gestion implicite du rowspan via colonnes présentes
    tbody = table.find("tbody")
    if not tbody:
        return None, source_url

    vals = {"deductible": None, "non_deductible_csg": None, "non_deductible_crds": None}
    for tr in tbody.find_all("tr"):
        tds = tr.find_all("td")
        if not tds:
            continue

        # libellé en col 0
        label = tds[0].get_text(" ", strip=True)

        # colonne "Salarié" dépend de la première ligne à 5 colonnes (rowspan) puis 4
        salarie_idx = 3 if len(tds) >= 5 else 2
        if len(tds) <= salarie_idx:
            continue
        val_txt = tds[salarie_idx].get_text(" ", strip=True)
        rate = parse_taux(val_txt)
        if rate is None:
            continue

        label_lower = label.lower()
        if "csg déductible" in label_lower or "csg deductible" in label_lower:
            vals["deductible"] = rate
        elif "csg non déductible" in label_lower or "csg non deductible" in label_lower:
            vals["non_deductible_csg"] = rate
        elif (
            "crds non déductible" in label_lower or "crds non deductible" in label_lower
        ):
            vals["non_deductible_crds"] = rate

        if all(v is not None for v in vals.values()):
            break

    if any(v is None for v in vals.values()):
        return None, source_url

    non_deductible = round(vals["non_deductible_csg"] + vals["non_deductible_crds"], 6)
    return {"deductible": vals["deductible"], "non_deductible": non_deductible}, source_url


def build_payload(taux: dict | None, source_url: str) -> dict:
    vals = {"salarial": None, "patronal": None}
    if taux is not None:
        vals["salarial"] = {
            "deductible": taux.get("deductible"),
            "non_deductible": taux.get("non_deductible"),
        }
    return {
        "id": "csg",
        "type": "cotisation",
        "libelle": "CSG/CRDS",
        "base": "brut",
        "valeurs": vals,
        "meta": {
            "source": [
                {
                    "url": source_url,
                    "label": "LégiSocial — Taux cotisations URSSAF 2025",
                    "date_doc": "",
                }
            ],
            "scraped_at": iso_now(),
            "generator": "scripts/CSG/CSG_LegiSocial.py",
            "method": "secondary",
        },
    }


if __name__ == "__main__":
    taux, source_url = get_taux_csg_legisocial()
    payload = build_payload(taux, source_url)
    print(json.dumps(payload, ensure_ascii=False))
