"""Registre des sources officielles — aligné sur scraping_sources (page Suivi des taux)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Optional

from supabase import Client

logger = logging.getLogger(__name__)

# Aligné sur rate_source_mapping.RATE_KEY_TO_SOURCE_KEYS (sans dépendance app).
RATE_KEY_TO_SOURCE_KEYS: dict[str, list[str]] = {
    "smic": ["SMIC"],
    "pss": ["PSS"],
    "ij_plafonds": ["IJ_MALADIE"],
    "pas": ["PAS"],
    "frais_pro": ["FRAIS_PRO"],
    "avantages_en_nature": ["AVANTAGES"],
    "heures_supp": ["HEURES_SUPP"],
    "primes": ["PRIMES"],
    "baremes_km": ["BAREME_INDEMNITE_KILOMETRIQUE"],
    "taux_vmrr": ["VM"],
    "cotisations": [
        "AGIRC-ARRCO", "AGS", "CSG", "CSA", "FNAL", "ALLOCATIONS_FAMILIALES",
        "ASSURANCE_CHOMAGE", "DIALOGUE_SOCIAL", "MMID_PATRONAL", "MMID_SALARIAL",
        "VIEILLESSE_PATRONAL", "VIEILLESSE_SALARIAL", "CFP", "TAXE_APPRENTISSAGE",
        "PREVOYANCE_CADRE", "PREVOYANCE_NON_CADRE",
    ],
}


def normalize_source_key(key: str) -> str:
    return key.strip().upper().replace("-", "_")

SOURCES_TABLE = "scraping_sources"


@dataclass(frozen=True)
class OfficialSource:
    """Source officielle canonique pour un scraper / taux."""

    source_key: str
    source_name: str
    primary_url: str
    alternative_urls: list[str]
    target_field: str
    scraper_name: str
    source_id: Optional[str] = None

    @property
    def all_urls(self) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for u in [self.primary_url, *self.alternative_urls]:
            if u and u not in seen:
                seen.add(u)
                out.append(u)
        return out


# Mapping manifest scraper_name → source_key DB (exceptions de nommage).
SCRAPER_TO_SOURCE_KEY: dict[str, str] = {
    "SMIC": "SMIC",
    "PSS": "PSS",
    "PAS": "PAS",
    "CSG": "CSG",
    "dialoguesocial": "DIALOGUE_SOCIAL",
    "AGS": "AGS",
    "CSA": "CSA",
    "alloc": "ALLOCATIONS_FAMILIALES",
    "assurancechomage": "ASSURANCE_CHOMAGE",
    "vieillessepatronal": "VIEILLESSE_PATRONAL",
    "vieillessesalarial": "VIEILLESSE_SALARIAL",
    "CFP": "CFP",
    "FNAL": "FNAL",
    "MMIDpatronal": "MMID_PATRONAL",
    "MMIDsalarial": "MMID_SALARIAL",
    "AGIRC-ARRCO": "AGIRC-ARRCO",
    "taxeapprentissage": "TAXE_APPRENTISSAGE",
    "PREVOYANCE_CADRE": "PREVOYANCE_CADRE",
    "PREVOYANCE_NON_CADRE": "PREVOYANCE_NON_CADRE",
    "IJmaladie": "IJ_MALADIE",
    "fraispro": "FRAIS_PRO",
    "Avantages": "AVANTAGES",
    "bareme-indemnite-kilometrique": "BAREME_INDEMNITE_KILOMETRIQUE",
    "VM": "VM",
    "heuressupp": "HEURES_SUPP",
    "primes": "PRIMES",
}


def scraper_to_source_key(scraper_name: str) -> str:
    return SCRAPER_TO_SOURCE_KEY.get(scraper_name, scraper_name.upper().replace("-", "_"))


def scraper_name_for_source_key(source_key: str) -> str:
    """Nom manifest scraper à partir de source_key DB."""
    norm = normalize_source_key(source_key)
    for scraper, db_key in SCRAPER_TO_SOURCE_KEY.items():
        if normalize_source_key(db_key) == norm:
            return scraper
    return source_key


def source_keys_for_rate_key(rate_key: str) -> list[str]:
    return RATE_KEY_TO_SOURCE_KEYS.get(rate_key, [])


def _parse_alternative_urls(raw: Any) -> list[str]:
    if isinstance(raw, list):
        return [u for u in raw if isinstance(u, str) and u.strip()]
    if isinstance(raw, dict):
        return [u for u in raw.values() if isinstance(u, str) and u.strip()]
    return []


def row_to_official_source(row: dict[str, Any], scraper_name: str) -> OfficialSource:
    return OfficialSource(
        source_id=row.get("id"),
        source_key=row.get("source_key", ""),
        source_name=row.get("source_name", ""),
        primary_url=(row.get("primary_url") or "").strip(),
        alternative_urls=_parse_alternative_urls(row.get("alternative_urls")),
        target_field=row.get("target_field") or "",
        scraper_name=scraper_name,
    )


def fetch_official_source(
    supabase: Client,
    scraper_name: str,
) -> Optional[OfficialSource]:
    """Charge la source officielle depuis scraping_sources (Suivi des taux)."""
    source_key = scraper_to_source_key(scraper_name)
    try:
        resp = (
            supabase.table(SOURCES_TABLE)
            .select("*")
            .eq("source_key", source_key)
            .eq("is_active", True)
            .limit(1)
            .execute()
        )
        if resp.data:
            return row_to_official_source(resp.data[0], scraper_name)
    except Exception as exc:
        logger.warning("fetch_official_source(%s): %s", scraper_name, exc)
    return None


def fetch_all_official_sources(supabase: Client) -> list[OfficialSource]:
    """Toutes les sources actives."""
    try:
        resp = (
            supabase.table(SOURCES_TABLE)
            .select("*")
            .eq("is_active", True)
            .order("source_key")
            .execute()
        )
        rows = resp.data or []
    except Exception as exc:
        logger.warning("fetch_all_official_sources: %s", exc)
        return []

    key_to_scraper = {v: k for k, v in SCRAPER_TO_SOURCE_KEY.items()}
    out: list[OfficialSource] = []
    for row in rows:
        sk = row.get("source_key", "")
        scraper = key_to_scraper.get(sk, sk)
        out.append(row_to_official_source(row, scraper))
    return out


def official_urls_for_rate_display(
    supabase: Client,
    rate_key: str,
    existing_links: list[str] | None,
) -> list[str]:
    """Fusionne primary_url officielle + liens scrapés pour l'affichage Suivi des taux."""
    seen: set[str] = set()
    merged: list[str] = []

    for sk in source_keys_for_rate_key(rate_key):
        norm = normalize_source_key(sk)
        for mapping_key, db_key in SCRAPER_TO_SOURCE_KEY.items():
            if normalize_source_key(db_key) == norm:
                src = fetch_official_source(supabase, mapping_key)
                if src and src.primary_url and src.primary_url not in seen:
                    seen.add(src.primary_url)
                    merged.append(src.primary_url)
                break

    for link in existing_links or []:
        if link and link not in seen:
            seen.add(link)
            merged.append(link)
    return merged


def update_primary_url(
    supabase: Client,
    source_id: str,
    new_url: str,
    *,
    validated_at: str | None = None,
) -> None:
    """Met à jour primary_url dans scraping_sources après validation."""
    payload: dict[str, Any] = {
        "primary_url": new_url,
        "updated_at": validated_at,
    }
    if validated_at:
        payload["url_validated_at"] = validated_at
        payload["url_validation_status"] = "valid"
    supabase.table(SOURCES_TABLE).update(payload).eq("id", source_id).execute()


def _normalize_url(url: str) -> str:
    return url.strip().rstrip("/")


def _is_legisocial_url(url: str) -> bool:
    host = url.lower()
    return "legisocial.fr" in host


def _fetch_active_payroll_config(
    supabase: Client,
    config_key: str,
) -> Optional[dict[str, Any]]:
    try:
        resp = (
            supabase.table("payroll_config")
            .select("id, source_links")
            .eq("config_key", config_key)
            .eq("is_active", True)
            .maybe_single()
            .execute()
        )
        return resp.data if resp is not None else None
    except Exception as exc:
        logger.warning("fetch payroll_config(%s): %s", config_key, exc)
        return None


def refresh_payroll_source_links_for_rate_key(
    supabase: Client,
    rate_key: str,
) -> bool:
    """Réaligne source_links d'une carte taux sur scraping_sources.primary_url."""
    row = _fetch_active_payroll_config(supabase, rate_key)
    if not row:
        return False

    existing = row.get("source_links") or []
    if isinstance(existing, str):
        existing = [existing]
    if not isinstance(existing, list):
        existing = []

    merged = official_urls_for_rate_display(supabase, rate_key, existing)
    if merged == existing:
        return False

    supabase.table("payroll_config").update({"source_links": merged}).eq(
        "id", row["id"]
    ).execute()
    logger.info("source_links mis à jour pour payroll_config.%s", rate_key)
    return True


def refresh_cotisations_source_links(supabase: Client) -> bool:
    """Réaligne source_links du bloc cotisations (URLs officielles + LegiSocial)."""
    row = _fetch_active_payroll_config(supabase, "cotisations")
    if not row:
        return False

    existing = row.get("source_links") or []
    if isinstance(existing, str):
        existing = [existing]
    if not isinstance(existing, list):
        existing = []

    seen: set[str] = set()
    merged: list[str] = []

    for source_keys in RATE_KEY_TO_SOURCE_KEYS["cotisations"]:
        norm = normalize_source_key(source_keys)
        for scraper, db_key in SCRAPER_TO_SOURCE_KEY.items():
            if normalize_source_key(db_key) != norm:
                continue
            src = fetch_official_source(supabase, scraper)
            if src and src.primary_url:
                key = _normalize_url(src.primary_url)
                if key not in seen:
                    seen.add(key)
                    merged.append(src.primary_url)
            break

    for link in existing:
        if not isinstance(link, str) or not link.strip():
            continue
        key = _normalize_url(link)
        if key in seen:
            continue
        if _is_legisocial_url(link):
            seen.add(key)
            merged.append(link.strip())

    if merged == existing:
        return False

    supabase.table("payroll_config").update({"source_links": merged}).eq(
        "id", row["id"]
    ).execute()
    logger.info("source_links mis à jour pour payroll_config.cotisations")
    return True


def refresh_all_payroll_source_links(supabase: Client) -> dict[str, Any]:
    """Propage les primary_url validées vers les cartes Suivi des taux."""
    updated_rate_keys: list[str] = []
    for rate_key in RATE_KEY_TO_SOURCE_KEYS:
        if rate_key == "cotisations":
            continue
        if refresh_payroll_source_links_for_rate_key(supabase, rate_key):
            updated_rate_keys.append(rate_key)

    cotisations_updated = refresh_cotisations_source_links(supabase)
    return {
        "rate_keys_updated": updated_rate_keys,
        "cotisations_updated": cotisations_updated,
    }
