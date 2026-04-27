# scripts/Avantages/Avantages_LegiSocial.py

import json
import re
import sys
from datetime import datetime
from typing import Optional, Dict, List

import requests
from bs4 import BeautifulSoup

URL_REPAS_TEMPLATE = (
    "https://www.legisocial.fr/reperes-sociaux/avantage-en-nature-repas-{year}.html"
)
URL_LOGEMENT_TEMPLATE = (
    "https://www.legisocial.fr/reperes-sociaux/avantage-en-nature-logement-{year}.html"
)
UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
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


# ---------- helpers ----------
def _txt(el) -> str:
    return el.get_text(" ", strip=True) if el else ""


def parse_number(text: str) -> Optional[float]:
    if not text:
        return None
    cleaned = (
        text.replace("\u202f", "")
        .replace("\xa0", "")
        .replace("€", "")
        .replace(" ", "")
        .replace(".", "")  # retire séparateurs de milliers type 1.234,56
        .replace(",", ".")
        .strip()
    )
    m = re.search(r"(-?\d+(?:\.\d+)?)", cleaned)
    try:
        return float(m.group(1)) if m else None
    except Exception:
        return None


def make_payload(
    repas: Optional[float],
    titre_restaurant: Optional[float],
    logement_bareme: List[Dict],
    url_repas: str,
    url_logement: str,
) -> dict:
    return {
        "id": "avantages_en_nature",
        "type": "param_bundle",
        "items": [
            {"key": "repas_valeur_forfaitaire_eur", "value": repas},
            {"key": "titre_restaurant_exoneration_max_eur", "value": titre_restaurant},
            {"key": "logement_bareme_forfaitaire", "value": logement_bareme},
        ],
        "meta": {
            "source": [
                {"url": url_repas, "label": "LegiSocial (Repas)", "date_doc": ""},
                {
                    "url": url_logement,
                    "label": "LegiSocial (Logement)",
                    "date_doc": "",
                },
            ],
            "generator": "scripts/Avantages/Avantages_LegiSocial.py",
        },
    }


# ---------- scrapers ----------
def scrape_repas() -> tuple[Dict[str, Optional[float]], str]:
    r = fetch_legisocial(URL_REPAS_TEMPLATE)
    soup = BeautifulSoup(r.text, "lxml")

    repas_val = None
    titre_exo = None

    table = soup.find("table")
    if not table:
        return {"repas": None, "titre": None}, r.url

    for tr in table.find_all("tr"):
        tds = tr.find_all("td")
        if len(tds) != 2:
            continue
        lib = _txt(tds[0]).lower()
        val = parse_number(_txt(tds[1]))
        if val is None:
            continue

        # valeur forfaitaire repas standard (hors HCR)
        if "avantage en nature repas (1 repas)" in lib and "hcr" not in lib:
            repas_val = val
        # participation patronale maximum tickets restaurant
        if "participation patronale maximum sur tickets restaurant" in lib:
            titre_exo = val

    return {"repas": repas_val, "titre": titre_exo}, r.url


def scrape_logement() -> tuple[List[Dict], str]:
    r = fetch_legisocial(URL_LOGEMENT_TEMPLATE)
    soup = BeautifulSoup(r.text, "lxml")

    header = None
    for h3 in soup.find_all("h3"):
        if (
            "méthode de l’évaluation forfaitaire" in _txt(h3).lower()
            or "methode de l’evaluation forfaitaire" in _txt(h3).lower()
            or "méthode de l'evaluation forfaitaire" in _txt(h3).lower()
        ):
            header = h3
            break
    if not header:
        return [], r.url

    table = header.find_next("table")
    if not table:
        return [], r.url

    tbody = table.find("tbody") or table
    rows = tbody.find_all("tr")
    if len(rows) < 3:
        return [], r.url

    # structure attendue : 3 lignes (tranches / 1 pièce / par pièce suppl.)
    tranches = rows[0].find_all("td")[1:]
    v1 = rows[1].find_all("td")[1:]
    vpp = rows[2].find_all("td")[1:]

    out: List[Dict] = []
    for i in range(min(len(tranches), len(v1), len(vpp))):
        tranche_txt = _txt(tranches[i])
        # dernière valeur numérique de la tranche = plafond (sinon inf)
        nums = re.findall(r"(\d[\d\s\u202f\u00a0\.,]*)", tranche_txt)
        rem_max = parse_number(nums[-1]) if nums else None
        out.append(
            {
                "remuneration_max_eur": rem_max
                if rem_max is not None
                else float("inf"),
                "valeur_1_piece_eur": parse_number(_txt(v1[i])),
                "valeur_par_piece_suppl_eur": parse_number(_txt(vpp[i])),
            }
        )

    # filtre les lignes incomplètes
    out = [
        b
        for b in out
        if b["valeur_1_piece_eur"] is not None
        and b["valeur_par_piece_suppl_eur"] is not None
    ]
    return out, r.url


# ---------- main ----------
if __name__ == "__main__":
    try:
        repas, url_repas = scrape_repas()
        logement, url_logement = scrape_logement()

        payload = make_payload(
            repas=repas.get("repas"),
            titre_restaurant=repas.get("titre"),
            logement_bareme=logement,
            url_repas=url_repas,
            url_logement=url_logement,
        )

        # succès si on a au moins repas ET titre_restaurant ET >=1 tranche logement
        ok = (
            payload["items"][0]["value"] is not None
            and payload["items"][1]["value"] is not None
            and isinstance(payload["items"][2]["value"], list)
            and len(payload["items"][2]["value"]) > 0
        )

        print(json.dumps(payload, ensure_ascii=False))
        sys.exit(0 if ok else 2)
    except Exception:
        # en échec, renvoyer structure vide mais valide
        y = datetime.now().year
        empty = make_payload(
            None,
            None,
            [],
            url_repas=URL_REPAS_TEMPLATE.format(year=y),
            url_logement=URL_LOGEMENT_TEMPLATE.format(year=y),
        )
        print(json.dumps(empty, ensure_ascii=False))
        sys.exit(2)
