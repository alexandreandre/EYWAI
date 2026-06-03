# scripts/PAS/PAS.py

import json
import re
import sys
import unicodedata
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://bofip.impots.gouv.fr"
# Page série BOI-BAREME-000037 (liste des versions publiées)
SERIE_PAGE_URL = f"{BASE_URL}/bofip/11255-PGP.html"
# Dernière version connue (BOI-BAREME-000037 du 07/04/2026, applicable au 1er mai 2026)
FALLBACK_DOCUMENT_URL = (
    f"{BASE_URL}/bofip/11255-PGP.html/identifiant%3DBOI-BAREME-000037-20260407"
)

NBSP = "\xa0"
NNBSP = "\u202f"
THIN = "\u2009"


def norm(txt: str) -> str:
    if not txt:
        return ""
    txt = txt.strip().lower()
    txt = unicodedata.normalize("NFD", txt)
    return "".join(ch for ch in txt if unicodedata.category(ch) != "Mn")


def get_latest_bofip_url() -> str:
    """
    Récupère l'URL de la dernière version publiée de BOI-BAREME-000037
    depuis la page série BOFIP, sinon repli sur l'URL documentée.
    """
    try:
        resp = requests.get(
            SERIE_PAGE_URL,
            timeout=20,
            headers={"User-Agent": "Mozilla/5.0", "Accept-Language": "fr-FR"},
        )
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            candidates: list[tuple[str, str]] = []
            for link in soup.find_all("a", href=True):
                href = link["href"]
                if "BOI-BAREME-000037" not in href:
                    continue
                if any(
                    bad in href.lower()
                    for bad in ("facebook.com", "twitter.com", "linkedin.com", "mailto:")
                ):
                    continue
                url = href if href.startswith("http") else BASE_URL + href
                if "bofip.impots.gouv.fr/bofip/" not in url.lower():
                    continue
                date_match = re.search(r"BOI-BAREME-000037-(\d{8})", href)
                date_key = date_match.group(1) if date_match else "00000000"
                candidates.append((date_key, url))
            if candidates:
                candidates.sort(key=lambda x: x[0], reverse=True)
                chosen = candidates[0][1]
                print(f"[PAS] Version BOFIP la plus récente : {chosen}", file=sys.stderr)
                return chosen
    except Exception as e:
        print(f"[PAS] Lecture page série BOFIP échouée : {e}", file=sys.stderr)

    print(f"[PAS] Repli sur URL documentée : {FALLBACK_DOCUMENT_URL}", file=sys.stderr)
    return FALLBACK_DOCUMENT_URL


# -------- Helpers --------
def iso_now() -> str:
    """Retourne la date et l'heure actuelles au format ISO 8601 UTC."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _clean_amount(txt: str) -> float:
    s = txt.strip().replace(NBSP, "").replace(NNBSP, "").replace(THIN, "")
    s = s.replace(" ", "").replace(".", "").replace(",", ".")
    m = re.search(r"(\d+(?:\.\d+)?)", s)
    return float(m.group(1)) if m else 0.0


def _clean_percent(txt: str) -> float:
    s = (
        txt.strip()
        .replace(NBSP, "")
        .replace(NNBSP, "")
        .replace(THIN, "")
        .replace(" ", "")
    )
    s = s.replace("%", "").replace(",", ".")
    m = re.search(r"(\d+(?:\.\d+)?)", s)
    return round(float(m.group(1)) / 100.0, 5) if m else 0.0


def _upper_bound_from_label(label: str) -> float | None:
    low = norm(label)
    nums = re.findall(r"\d[\d\s\u00A0\u202F\u2009\.]*", label)
    if not nums:
        return None
    if "inferieure a" in low and "superieure" not in low:
        return _clean_amount(nums[-1])
    if "superieure ou egale" in low and "inferieure a" in low and len(nums) >= 2:
        return _clean_amount(nums[1])
    if "superieure ou egale" in low and "inferieure a" not in low:
        return None
    return _clean_amount(nums[-1])


def _zone_from_caption(caption: str) -> str | None:
    c = norm(caption)
    if any(k in c for k in ["guyane", "mayotte"]):
        return "guyane_mayotte"
    if any(k in c for k in ["guadeloupe", "reunion", "martinique"]):
        return "guadeloupe_reunion_martinique"
    if any(k in c for k in ["metropole", "hors de france"]):
        return "metropole"
    return None


def _extract_tranches_from_table(table: BeautifulSoup) -> list[dict]:
    tranches = []
    for tr in table.find_all("tr"):
        tds = tr.find_all(["td", "th"])
        if len(tds) < 2:
            continue
        label = tds[0].get_text(" ", strip=True)
        taux_txt = tds[1].get_text(" ", strip=True)
        if not label or "%" not in taux_txt:
            continue
        plafond = _upper_bound_from_label(label)
        taux = _clean_percent(taux_txt)
        tranches.append({"plafond": plafond, "taux": taux})
    return tranches


def _parse_zones_from_soup(soup: BeautifulSoup) -> dict[str, list[dict]]:
    zones: dict[str, list[dict] | None] = {
        "metropole": None,
        "guadeloupe_reunion_martinique": None,
        "guyane_mayotte": None,
    }

    for tbl in soup.find_all("table"):
        caption_el = tbl.find("caption")
        caption = caption_el.get_text(" ", strip=True) if caption_el else ""
        if not caption:
            prev = tbl.find_previous(["h1", "h2", "h3"])
            if prev:
                caption = prev.get_text(" ", strip=True)
        zone_key = _zone_from_caption(caption)
        if not zone_key or zones.get(zone_key):
            continue
        tranches = _extract_tranches_from_table(tbl)
        if tranches:
            zones[zone_key] = tranches

    if not zones["metropole"]:
        raise ValueError("Table pour la métropole non trouvée ou vide.")
    if not zones["guadeloupe_reunion_martinique"]:
        raise ValueError(
            "Table pour Guadeloupe/Réunion/Martinique non trouvée ou vide."
        )
    if not zones["guyane_mayotte"]:
        raise ValueError("Table pour Guyane/Mayotte non trouvée ou vide.")
    return zones  # type: ignore[return-value]


def fetch_bofip_soup(url: str) -> BeautifulSoup:
    r = requests.get(
        url,
        timeout=30,
        headers={"User-Agent": "Mozilla/5.0", "Accept-Language": "fr-FR,en;q=0.8"},
    )
    r.raise_for_status()
    return BeautifulSoup(r.text, "html.parser")


def zone_table_text(soup: BeautifulSoup, zone_key: str) -> str:
    """Texte du tableau BOFIP pour une zone (contexte Sonar ciblé)."""
    for tbl in soup.find_all("table"):
        caption_el = tbl.find("caption")
        caption = caption_el.get_text(" ", strip=True) if caption_el else ""
        if not caption:
            prev = tbl.find_previous(["h1", "h2", "h3"])
            if prev:
                caption = prev.get_text(" ", strip=True)
        if _zone_from_caption(caption) != zone_key:
            continue
        lines = [caption, ""]
        for tr in tbl.find_all("tr"):
            cells = [
                c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])
            ]
            if len(cells) >= 2 and "%" in cells[1]:
                lines.append(f"{cells[0]} | {cells[1]}")
        if len(lines) > 2:
            return "\n".join(lines)
    raise ValueError(f"Table BOFIP introuvable pour la zone {zone_key}.")


# -------- Scraper --------
def scrape_bofip(url: str) -> dict:
    print(f"Scraping de l'URL du BOFIP : {url}", file=sys.stderr)
    soup = fetch_bofip_soup(url)
    zones = _parse_zones_from_soup(soup)

    print(
        f"  - Données extraites : {len(zones['metropole'])} tranches (métropole), "
        f"{len(zones['guadeloupe_reunion_martinique'])} (GRM), "
        f"{len(zones['guyane_mayotte'])} (GM).",
        file=sys.stderr,
    )
    return zones


# -------- Main --------
def main():
    """Orchestre le scraping et génère la sortie JSON pour l'orchestrateur."""
    url_used = get_latest_bofip_url()
    print(f"[PAS] URL BOFIP utilisée : {url_used}", file=sys.stderr)
    try:
        zones_data = scrape_bofip(url_used)
    except Exception as e:
        print(
            f"ERREUR CRITIQUE: Le scraping du PAS a échoué. Raison : {e}",
            file=sys.stderr,
        )
        sys.exit(1)

    payload = {
        "id": "pas_taux_neutre",
        "type": "bareme_imposition",
        "libelle": "Prélèvement à la Source (PAS) - Grille de taux par défaut",
        "sections": zones_data,
        "meta": {
            "source": [
                {
                    "url": url_used,
                    "label": "BOFIP - Barème du prélèvement à la source",
                    "date_doc": "",
                }
            ],
            "scraped_at": iso_now(),
            "generator": "scripts/PAS/PAS.py",
            "method": "primary",
        },
    }

    print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
