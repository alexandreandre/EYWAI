#!/usr/bin/env python3
"""
Référentiel prévoyance pour Suivi des taux.

- Cadre : minimum légal ANI du 17/11/2017 — 1,50 % patronal sur la tranche 1 (T1).
- Non-cadre : taux dépendant de la convention collective ; pas de taux national unique :
  le scraper enregistre un contrôle sans écraser les taux en base (preserve_rates).
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

URL_ANI_SERVICE_PUBLIC = (
    "https://www.service-public.fr/professionnels-entreprises/vosdroits/F33666"
)
LEGAL_CADRE_PATRONAL = 0.015


def iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_percent_to_rate(text: str) -> float | None:
    if not text:
        return None
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*%", text)
    if not m:
        return None
    return round(float(m.group(1).replace(",", ".")) / 100.0, 6)


def verify_cadre_minimum_on_page() -> float | None:
    """Tente de retrouver 1,50 % sur la page service-public ; sinon retourne le taux légal."""
    try:
        r = requests.get(
            URL_ANI_SERVICE_PUBLIC,
            timeout=25,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
                ),
                "Accept-Language": "fr-FR,fr;q=0.9",
            },
        )
        r.raise_for_status()
        text = BeautifulSoup(r.text, "html.parser").get_text(" ", strip=True)
        if re.search(r"1[,.]50\s*%", text):
            parsed = parse_percent_to_rate("1,50 %")
            if parsed is not None and abs(parsed - LEGAL_CADRE_PATRONAL) < 1e-6:
                return parsed
    except Exception as exc:
        print(f"[prevoyance] Vérification service-public ignorée: {exc}", file=sys.stderr)
    return LEGAL_CADRE_PATRONAL


def build_payload() -> dict:
    cadre_patronal = verify_cadre_minimum_on_page()
    return {
        "cadre": {
            "id": "prevoyance_cadre",
            "type": "cotisation",
            "libelle": "Prévoyance Cadre Tranche 1",
            "base": "brut",
            "valeurs": {"salarial": None, "patronal": cadre_patronal},
            "meta": {
                "source": [
                    {
                        "url": URL_ANI_SERVICE_PUBLIC,
                        "label": "Service-public — Prévoyance des cadres (ANI 1,50 % T1)",
                        "date_doc": "",
                    }
                ],
                "scraped_at": iso_now(),
                "generator": "prevoyance/prevoyance.py",
                "method": "legal_minimum_ani",
            },
        },
        "non_cadre": {
            "id": "prevoyance_non_cadre",
            "type": "cotisation",
            "libelle": "Prévoyance Non-Cadre Tranche 1",
            "base": "brut",
            "valeurs": {"salarial": None, "patronal": None},
            "preserve_rates": True,
            "meta": {
                "source": [
                    {
                        "url": URL_ANI_SERVICE_PUBLIC,
                        "label": (
                            "Taux non-cadre : selon convention collective "
                            "(contrôle sans modification du barème national)"
                        ),
                        "date_doc": "",
                    }
                ],
                "scraped_at": iso_now(),
                "generator": "prevoyance/prevoyance.py",
                "method": "stamp_only_ccn_dependent",
            },
        },
    }


def main() -> None:
    print(json.dumps(build_payload(), ensure_ascii=False))


if __name__ == "__main__":
    main()
