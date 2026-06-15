"""Recherche textuelle sur les conventions collectives (catalogue)."""

from __future__ import annotations

import re
import unicodedata
from typing import Any


def normalize_search_text(text: str) -> str:
    if not text:
        return ""
    nfkd = unicodedata.normalize("NFD", str(text))
    stripped = "".join(c for c in nfkd if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", stripped.lower()).strip()


def search_tokens(query: str) -> list[str]:
    normalized = normalize_search_text(query)
    if not normalized:
        return []
    tokens = [token for token in normalized.split(" ") if len(token) >= 2 or token.isdigit()]
    return tokens or [normalized]


def agreement_search_blob(agreement: dict[str, Any]) -> str:
    parts = [
        agreement.get("name") or "",
        agreement.get("idcc") or "",
        agreement.get("sector") or "",
        agreement.get("description") or "",
    ]
    return normalize_search_text(" ".join(str(part) for part in parts if part))


def matches_agreement_search(agreement: dict[str, Any], query: str) -> bool:
    cleaned = query.strip()
    if not cleaned:
        return True
    blob = agreement_search_blob(agreement)
    return all(token in blob for token in search_tokens(cleaned))


def rank_agreement_search(agreement: dict[str, Any], query: str) -> int:
    cleaned = query.strip()
    if not cleaned:
        return 0

    blob = agreement_search_blob(agreement)
    tokens = search_tokens(cleaned)
    score = 0

    idcc = normalize_search_text(str(agreement.get("idcc") or ""))
    query_norm = normalize_search_text(cleaned)
    if idcc and (query_norm == idcc or query_norm == idcc.lstrip("0")):
        score += 200
    elif idcc and query_norm.isdigit() and idcc.startswith(query_norm):
        score += 150

    name = normalize_search_text(str(agreement.get("name") or ""))
    sector = normalize_search_text(str(agreement.get("sector") or ""))

    for token in tokens:
        if name.startswith(token):
            score += 80
        elif token in name:
            score += 50
        if token in sector:
            score += 40
        if token in blob:
            score += 10

    return score


def filter_and_rank_agreements(
    agreements: list[dict[str, Any]],
    query: str,
    *,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    cleaned = query.strip()
    if not cleaned:
        ordered = list(agreements)
    else:
        matched = [item for item in agreements if matches_agreement_search(item, cleaned)]
        ordered = sorted(
            matched,
            key=lambda item: (-rank_agreement_search(item, cleaned), str(item.get("name") or "")),
        )
    if limit is not None:
        return ordered[:limit]
    return ordered
