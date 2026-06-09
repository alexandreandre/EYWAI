"""Croisement propositions CC ↔ catalogue entreprise."""

from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, List, Optional


def normalize_training_title(title: str) -> str:
    s = unicodedata.normalize("NFKD", title or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return " ".join(s.split())


def build_catalog_match_maps(
    catalog_rows: List[Dict[str, Any]],
) -> tuple[Dict[str, str], Dict[str, str]]:
    """Retourne (reco_id -> training_id, normalized_title -> training_id)."""
    by_reco: Dict[str, str] = {}
    by_title: Dict[str, str] = {}
    for row in catalog_rows:
        tid = str(row.get("id") or "")
        if not tid:
            continue
        reco_id = row.get("source_cc_recommendation_id")
        if reco_id:
            by_reco[str(reco_id)] = tid
        title_key = normalize_training_title(str(row.get("title") or ""))
        if title_key and title_key not in by_title:
            by_title[title_key] = tid
    return by_reco, by_title


def match_recommendation_to_catalog(
    reco: Dict[str, Any],
    *,
    by_reco: Dict[str, str],
    by_title: Dict[str, str],
) -> tuple[bool, Optional[str]]:
    reco_id = str(reco.get("id") or "")
    if reco_id and reco_id in by_reco:
        return True, by_reco[reco_id]
    title_key = normalize_training_title(str(reco.get("title") or ""))
    if title_key and title_key in by_title:
        return True, by_title[title_key]
    return False, None
