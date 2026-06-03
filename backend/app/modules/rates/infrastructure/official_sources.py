"""
Fusion des URLs officielles (scraping_sources.primary_url) dans source_links des taux.

Alimente la page Suivi des taux : la source canonique précède les liens scrapés.
"""

from __future__ import annotations

from typing import Any

from app.core.database import get_supabase_admin_client
from app.modules.rates.domain.rate_source_mapping import RATE_KEY_TO_SOURCE_KEYS

SOURCES_TABLE = "scraping_sources"


def _fetch_primary_urls_by_source_key() -> dict[str, str]:
    supabase = get_supabase_admin_client()
    resp = (
        supabase.table(SOURCES_TABLE)
        .select("source_key, primary_url")
        .eq("is_active", True)
        .execute()
    )
    out: dict[str, str] = {}
    for row in resp.data or []:
        key = (row.get("source_key") or "").strip().upper().replace("-", "_")
        url = (row.get("primary_url") or "").strip()
        if key and url:
            out[key] = url
    return out


def merge_official_urls_into_rates(
    grouped: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Enrichit source_links de chaque config_key avec primary_url officielle."""
    primary_by_key = _fetch_primary_urls_by_source_key()
    if not primary_by_key:
        return grouped

    result: dict[str, dict[str, Any]] = {}
    for config_key, row in grouped.items():
        merged = dict(row)
        seen: set[str] = set()
        official_links: list[str] = []

        for sk in RATE_KEY_TO_SOURCE_KEYS.get(config_key, []):
            norm = sk.strip().upper().replace("-", "_")
            url = primary_by_key.get(norm)
            if url and url not in seen:
                seen.add(url)
                official_links.append(url)

        existing = merged.get("source_links") or []
        if isinstance(existing, str):
            existing = [existing]
        combined: list[str] = []
        for url in [*official_links, *(existing if isinstance(existing, list) else [])]:
            if url and url not in seen:
                seen.add(url)
                combined.append(url)
        merged["source_links"] = combined or None
        result[config_key] = merged
    return result
