#!/usr/bin/env python3
"""Source primary IJSS — page officielle Service Public."""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from bs4 import BeautifulSoup

_SCRAPING = Path(__file__).resolve().parent.parent
if str(_SCRAPING) not in sys.path:
    sys.path.insert(0, str(_SCRAPING))

from core.http import build_session, fetch_html  # noqa: E402

URL_SERVICE_PUBLIC = (
    "https://www.service-public.gouv.fr/particuliers/actualites/A18779"
)

PATTERNS = {
    "maladie": re.compile(
        r"maladie,\s*à\s*([\d\s,\.\u202f\u00a0]+)\s*€",
        re.IGNORECASE,
    ),
    "maternite_paternite": re.compile(
        r"maternité et de paternité,\s*à\s*([\d\s,\.\u202f\u00a0]+)\s*€",
        re.IGNORECASE,
    ),
    "at_mp": re.compile(
        r"([\d\s,\.\u202f\u00a0]+)\s*€/jour pendant les 28",
        re.IGNORECASE,
    ),
    "at_mp_majoree": re.compile(
        r"([\d\s,\.\u202f\u00a0]+)\s*€/jour à partir du 29",
        re.IGNORECASE,
    ),
}


def parse_montant(text: str) -> float:
    cleaned = (
        text.replace("\xa0", "")
        .replace("\u202f", "")
        .replace(" ", "")
        .replace(",", ".")
        .strip()
    )
    match = re.search(r"\d+\.?\d*", cleaned)
    if not match:
        raise ValueError(f"Montant invalide: {text!r}")
    return float(match.group())


def extract_plafonds_ij(html: str) -> dict[str, float]:
    """Extrait les 4 plafonds IJSS depuis la page Service Public A18779."""
    text = BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
    if "Plafonds des indemnités journalières" not in text:
        raise ValueError("Section plafonds IJSS introuvable sur la page")

    plafonds: dict[str, float] = {}
    for key, pattern in PATTERNS.items():
        match = pattern.search(text)
        if not match:
            raise ValueError(f"Plafond IJ manquant: {key}")
        plafonds[key] = round(parse_montant(match.group(1)), 2)

    return plafonds


def get_plafonds_ij_service_public() -> tuple[dict[str, float], str]:
    print(f"Scraping de l'URL : {URL_SERVICE_PUBLIC}...", file=sys.stderr)
    html = fetch_html(URL_SERVICE_PUBLIC, session=build_session(), timeout=20)
    plafonds = extract_plafonds_ij(html)
    for key, value in plafonds.items():
        print(f"  - Plafond '{key}' : {value} €/jour", file=sys.stderr)
    return plafonds, URL_SERVICE_PUBLIC


def iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def main() -> None:
    plafonds, source_url = get_plafonds_ij_service_public()
    payload = {
        "id": "ij_maladie",
        "type": "secu",
        "libelle": "Indemnités journalières — montants maximums",
        "base": None,
        "valeurs": {
            **plafonds,
            "unite": "EUR/jour",
        },
        "meta": {
            "source": [
                {
                    "url": source_url,
                    "label": "Service Public — IJSS montants 2026",
                    "date_doc": "26/01/2026",
                }
            ],
            "scraped_at": iso_now(),
            "generator": "IJmaladie/IJmaladie.py",
            "method": "primary",
        },
    }
    print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
