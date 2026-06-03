#!/usr/bin/env python3
"""Tripwire : détecte un changement matériel d'une page officielle.

Cette couche n'écrit JAMAIS payroll_config. Elle prend un snapshot normalisé des
pages source, le compare au dernier snapshot connu, et lève une alerte si le
contenu a matériellement changé — afin de réparer le parser AVANT qu'il ne casse
silencieusement. Risque quasi nul (lecture + alerte uniquement).

Usage : python tripwire.py <source_key>
"""

from __future__ import annotations

import hashlib
import logging
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# Amorçage sys.path (comme les orchestrateurs) pour importer core.* / utils.
_SCRAPING = Path(__file__).resolve().parent.parent
if str(_SCRAPING) not in sys.path:
    sys.path.insert(0, str(_SCRAPING))

from core.env import ensure_scraping_path, load_env  # noqa: E402
from core.http import fetch_soup  # noqa: E402
from core.supabase_io import init_supabase_client  # noqa: E402

logger = logging.getLogger(__name__)

SNAPSHOT_TABLE = "scraping_page_snapshots"
ALERT_TABLE = "scraping_alerts"
SOURCES_TABLE = "scraping_sources"

_WHITESPACE_RE = re.compile(r"\s+")


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_page_text(soup: Any) -> str:
    """Texte normalisé d'une page : retire script/style, écrase les espaces.

    On vise un signal stable : un changement de chiffres/structure déclenche,
    pas une variation cosmétique (timestamps de rendu, espaces, etc.).
    """
    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()
    text = soup.get_text(separator=" ")
    text = _WHITESPACE_RE.sub(" ", text).strip()
    return text


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def collect_urls(source_row: Dict[str, Any]) -> List[str]:
    urls: List[str] = []
    primary = source_row.get("primary_url")
    if primary:
        urls.append(primary)
    alternative = source_row.get("alternative_urls")
    if isinstance(alternative, list):
        urls.extend(u for u in alternative if isinstance(u, str) and u)
    elif isinstance(alternative, dict):
        urls.extend(u for u in alternative.values() if isinstance(u, str) and u)
    # Dédoublonne en conservant l'ordre.
    seen: set[str] = set()
    return [u for u in urls if not (u in seen or seen.add(u))]


def _last_snapshot(supabase, url: str) -> Optional[Dict[str, Any]]:
    resp = (
        supabase.table(SNAPSHOT_TABLE)
        .select("*")
        .eq("url", url)
        .order("fetched_at", desc=True)
        .limit(1)
        .execute()
    )
    return resp.data[0] if resp.data else None


def _insert_snapshot(
    supabase,
    *,
    source_id: Optional[str],
    source_key: Optional[str],
    url: str,
    hash_value: str,
    excerpt: str,
    http_status: Optional[int],
) -> None:
    supabase.table(SNAPSHOT_TABLE).insert(
        {
            "source_id": source_id,
            "source_key": source_key,
            "url": url,
            "content_hash": hash_value,
            "normalized_excerpt": excerpt[:2000],
            "http_status": http_status,
            "fetched_at": _iso_now(),
        }
    ).execute()


def _create_change_alert(
    supabase,
    *,
    source_id: Optional[str],
    source_name: str,
    url: str,
    is_critical: bool,
) -> None:
    supabase.table(ALERT_TABLE).insert(
        {
            "source_id": source_id,
            "alert_type": "tripwire_change",
            "severity": "warning" if is_critical else "info",
            "title": f"Changement de page détecté : {source_name}",
            "message": (
                "La page officielle a matériellement changé. Vérifier le parser "
                "avant le prochain cycle (tripwire — aucune écriture effectuée)."
            ),
            "details": {"url": url},
        }
    ).execute()


def _enqueue_tripwire_repair(
    supabase,
    *,
    source_row: Dict[str, Any],
    url: str,
    excerpt: str,
) -> None:
    """Dépose un job repair agent après changement tripwire (tier critique)."""
    try:
        from agent.jobs import enqueue_repair_job
        from agent.source_registry import (
            fetch_official_source,
            scraper_name_for_source_key,
        )
        from agent.triggers import context_for_tripwire

        source_key = source_row.get("source_key") or ""
        scraper_name = scraper_name_for_source_key(source_key)
        official = fetch_official_source(supabase, scraper_name)
        official_url = (
            (official.primary_url if official else None)
            or source_row.get("primary_url")
            or url
        )
        enqueue_repair_job(
            supabase,
            scraper_name=scraper_name,
            trigger="tripwire_change",
            source_id=source_row.get("id"),
            error_message=f"Tripwire : changement DOM sur {url}",
            context=context_for_tripwire(
                url=url,
                excerpt=excerpt,
                official_url=official_url,
            ),
        )
    except Exception as exc:
        logger.warning("Enqueue repair tripwire échoué : %s", exc)


def run_tripwire_for_source(supabase, source_row: Dict[str, Any]) -> Dict[str, Any]:
    """Snapshot + diff de toutes les URLs d'une source. Ne touche pas payroll_config."""
    source_id = source_row.get("id")
    source_key = source_row.get("source_key")
    source_name = source_row.get("source_name") or source_key or "?"
    is_critical = bool(source_row.get("is_critical"))

    urls = collect_urls(source_row)
    if not urls:
        logger.warning("Aucune URL pour la source %s", source_name)
        return {"source_key": source_key, "checked": 0, "changed": [], "baseline": []}

    changed: List[str] = []
    baseline: List[str] = []

    for url in urls:
        http_status: Optional[int] = None
        try:
            soup = fetch_soup(url, use_selenium_on_forbidden=True)
            http_status = 200
        except Exception as exc:
            logger.warning("Tripwire fetch échoué %s: %s", url, exc)
            continue

        text = normalize_page_text(soup)
        new_hash = content_hash(text)
        previous = _last_snapshot(supabase, url)

        if previous is None:
            baseline.append(url)
            logger.info("Tripwire baseline créée pour %s", url)
        elif previous.get("content_hash") != new_hash:
            changed.append(url)
            logger.warning("Tripwire : changement détecté sur %s", url)
            _create_change_alert(
                supabase,
                source_id=source_id,
                source_name=source_name,
                url=url,
                is_critical=is_critical,
            )
            if is_critical:
                _enqueue_tripwire_repair(
                    supabase,
                    source_row=source_row,
                    url=url,
                    excerpt=text,
                )
        else:
            logger.info("Tripwire : page inchangée %s", url)

        _insert_snapshot(
            supabase,
            source_id=source_id,
            source_key=source_key,
            url=url,
            hash_value=new_hash,
            excerpt=text,
            http_status=http_status,
        )

    return {
        "source_key": source_key,
        "checked": len(urls),
        "changed": changed,
        "baseline": baseline,
    }


def _fetch_source(supabase, source_key: str) -> Optional[Dict[str, Any]]:
    resp = (
        supabase.table(SOURCES_TABLE)
        .select("*")
        .eq("source_key", source_key)
        .maybe_single()
        .execute()
    )
    return resp.data if resp and resp.data else None


def main() -> None:
    ensure_scraping_path()
    load_env()
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s [%(levelname)s] - %(message)s"
    )
    if len(sys.argv) < 2:
        print("Usage: python tripwire.py <source_key>", file=sys.stderr)
        sys.exit(64)

    source_key = sys.argv[1]
    supabase = init_supabase_client()
    source_row = _fetch_source(supabase, source_key)
    if source_row is None:
        logger.error("Source introuvable : %s", source_key)
        sys.exit(2)

    result = run_tripwire_for_source(supabase, source_row)
    logger.info(
        "Tripwire %s — %s URL(s), %s changement(s), %s baseline(s)",
        source_key,
        result["checked"],
        len(result["changed"]),
        len(result["baseline"]),
    )
    sys.exit(0)


if __name__ == "__main__":
    main()
