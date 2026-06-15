"""Enrichissement raison sociale via API recherche-entreprises (data.gouv.fr)."""

from __future__ import annotations

import logging
from typing import Optional

import requests

logger = logging.getLogger(__name__)

_LOOKUP_URL = "https://recherche-entreprises.api.gouv.fr/search"
_TIMEOUT = 5


def lookup_company_name_by_siren(siren: str) -> Optional[str]:
    """Retourne la dénomination légale ou None si indisponible."""
    clean = (siren or "").replace(" ", "")[:9]
    if len(clean) != 9 or not clean.isdigit():
        return None
    try:
        resp = requests.get(
            _LOOKUP_URL,
            params={"q": clean, "page": 1, "per_page": 1},
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        results = data.get("results") or []
        if not results:
            return None
        row = results[0]
        name = row.get("nom_complet") or row.get("nom_raison_sociale") or row.get("sigle")
        return str(name).strip() if name else None
    except Exception as exc:
        logger.warning("Lookup SIREN %s échoué : %s", clean, exc)
        return None
