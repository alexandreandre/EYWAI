"""Validation mensuelle des URLs officielles (scraping_sources.primary_url).

Vérifie chaque source via HTTP puis Sonar. Met à jour uniquement l'affichage
(primary_url + pastilles Suivi des taux) — sans modifier les scripts de scraping.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

_SCRAPING = Path(__file__).resolve().parent.parent
if str(_SCRAPING) not in sys.path:
    sys.path.insert(0, str(_SCRAPING))

from agent.models import MODEL_URL_SEARCH, OFFICIAL_DOMAINS, agent_disabled
from agent.prompts import DISPLAY_URL_DISCOVERY_SYSTEM, SOURCE_VALIDATION_SYSTEM
from agent.source_registry import (
    OfficialSource,
    fetch_all_official_sources,
    refresh_all_payroll_source_links,
    update_primary_url,
)
from agent.tools import check_url_alive
from core.env import ensure_scraping_path, load_env
from core.official_domains import host_is_official
from core.supabase_io import init_supabase_client
from supabase import Client

logger = logging.getLogger(__name__)

URL_VALIDATION_SCHEMA = {
    "type": "object",
    "properties": {
        "is_valid": {"type": "boolean"},
        "official_url": {"type": ["string", "null"]},
        "rationale": {"type": "string"},
    },
    "required": ["is_valid", "official_url", "rationale"],
    "additionalProperties": False,
}

DISPLAY_URL_DISCOVERY_SCHEMA = {
    "type": "object",
    "properties": {
        "official_url": {"type": "string"},
        "rationale": {"type": "string"},
    },
    "required": ["official_url", "rationale"],
    "additionalProperties": False,
}


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_url(url: str) -> str:
    return url.strip().rstrip("/")


def _call_sonar_json(
    *,
    system: str,
    user: str,
    schema: dict[str, Any],
    schema_name: str,
) -> Optional[dict[str, Any]]:
    try:
        from openrouter_client import chat_completions_create, require_api_key

        require_api_key()
    except Exception as exc:
        logger.warning("OpenRouter indisponible : %s", exc)
        return None

    plugins = [{"id": "web", "max_results": 10, "include_domains": OFFICIAL_DOMAINS}]
    try:
        resp = chat_completions_create(
            model=MODEL_URL_SEARCH,
            temperature=0,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": schema_name,
                    "strict": True,
                    "schema": schema,
                },
            },
            extra_body={"plugins": plugins},
        )
        raw = (resp.choices[0].message.content or "").strip()
        return json.loads(raw)
    except Exception as exc:
        logger.warning("Appel Sonar échoué (%s): %s", schema_name, exc)
        return None


def _verify_official_url_with_sonar(
    *,
    source_name: str,
    source_key: str,
    current_url: str,
    target_field: str,
    http_alive: bool,
    http_status: int,
    final_url: str,
) -> dict[str, Any]:
    """Sonar : l'URL enregistrée est-elle toujours la source officielle canonique ?"""
    fallback = {
        "official_url": current_url if http_alive else None,
        "action": "confirmed" if http_alive else "failed",
        "rationale": "Sonar indisponible — repli HTTP uniquement",
        "sonar_used": False,
    }

    http_hint = (
        f"accessible (HTTP {http_status}, URL finale après redirection : {final_url})"
        if http_alive
        else f"inaccessible ou erreur (HTTP {http_status})"
    )
    user = (
        f"Taux / barème : {source_name}\n"
        f"Clé source : {source_key}\n"
        f"Champ payroll cible : {target_field or '—'}\n"
        f"URL officielle enregistrée : {current_url}\n"
        f"État HTTP : {http_hint}\n\n"
        "Cette URL est-elle toujours la page officielle canonique pour consulter "
        "ce taux en France ? Si une autre page officielle est devenue la référence, "
        "indique-la. Si l'URL enregistrée reste correcte (y compris après redirection "
        "permanente vers la nouvelle URL canonique), confirme-la."
    )

    data = _call_sonar_json(
        system=SOURCE_VALIDATION_SYSTEM,
        user=user,
        schema=URL_VALIDATION_SCHEMA,
        schema_name="url_validation",
    )
    if not data:
        return fallback

    rationale = str(data.get("rationale") or "")
    official = data.get("official_url")
    is_valid = bool(data.get("is_valid"))

    if isinstance(official, str) and official.startswith("http") and host_is_official(official):
        chosen = official.strip()
    elif is_valid and http_alive:
        chosen = final_url.strip() if final_url.startswith("http") else current_url
    elif is_valid:
        chosen = current_url
    else:
        return {
            "official_url": None,
            "action": "failed",
            "rationale": rationale or "Sonar n'a pas confirmé l'URL enregistrée",
            "sonar_used": True,
        }

    if _normalize_url(chosen) == _normalize_url(current_url):
        return {
            "official_url": chosen,
            "action": "confirmed",
            "rationale": rationale,
            "sonar_used": True,
        }

    return {
        "official_url": chosen,
        "action": "updated",
        "rationale": rationale,
        "sonar_used": True,
    }


def _discover_display_url_with_sonar(
    *,
    source_name: str,
    source_key: str,
    current_url: str,
    target_field: str,
    prior_rationale: str = "",
) -> dict[str, Any]:
    """
    Second passage Sonar : trouve l'URL officielle à afficher quand la validation a échoué.
    Ne touche pas au scraping — uniquement la source documentaire des cartes.
    """
    user = (
        f"Taux / barème : {source_name}\n"
        f"Clé source : {source_key}\n"
        f"Champ payroll cible : {target_field or '—'}\n"
        f"Ancienne URL enregistrée (obsolète ou non validée) : {current_url}\n"
    )
    if prior_rationale:
        user += f"Contexte validation précédente : {prior_rationale}\n"
    user += (
        "\nTrouve la page officielle ACTUELLE à afficher aux utilisateurs RH "
        "pour consulter ce taux/barème en France."
    )

    data = _call_sonar_json(
        system=DISPLAY_URL_DISCOVERY_SYSTEM,
        user=user,
        schema=DISPLAY_URL_DISCOVERY_SCHEMA,
        schema_name="display_url_discovery",
    )
    if not data:
        return {
            "official_url": None,
            "action": "failed",
            "rationale": "Sonar indisponible pour la découverte d'URL d'affichage",
            "sonar_used": False,
        }

    official = data.get("official_url")
    rationale = str(data.get("rationale") or "")
    if isinstance(official, str) and official.startswith("http") and host_is_official(official):
        return {
            "official_url": official.strip(),
            "action": "updated",
            "rationale": rationale,
            "sonar_used": True,
        }

    return {
        "official_url": None,
        "action": "failed",
        "rationale": rationale or "Sonar n'a pas trouvé d'URL officielle de remplacement",
        "sonar_used": True,
    }


def _apply_display_url_update(
    supabase: Client,
    src: OfficialSource,
    *,
    new_url: str,
    detail: dict[str, Any],
    summary: dict[str, Any],
    discovery_fallback: bool = False,
) -> None:
    """Met à jour scraping_sources.primary_url pour l'affichage (sans toucher aux scrapers)."""
    old_url = src.primary_url
    update_primary_url(supabase, src.source_id, new_url, validated_at=_iso_now())
    summary["updated"] += 1
    detail["action"] = "updated"
    detail["new_url"] = new_url
    detail["display_only"] = True
    if discovery_fallback:
        detail["discovery_fallback"] = True
    logger.info(
        "Affichage source mis à jour pour %s : %s → %s",
        src.source_key,
        old_url,
        new_url,
    )


def validate_all_official_sources(
    supabase=None,
    *,
    refresh_display_links: bool = True,
) -> dict[str, Any]:
    """
    Vérifie chaque primary_url active (HTTP + Sonar mensuel).
    Met à jour scraping_sources.primary_url et payroll_config.source_links
    si Sonar propose une URL — sans modifier les scripts de scraping.
    """
    if agent_disabled():
        return {"skipped": True, "reason": "agent disabled"}

    ensure_scraping_path()
    load_env()
    supabase = supabase or init_supabase_client()

    sources = fetch_all_official_sources(supabase)
    summary: dict[str, Any] = {
        "checked": 0,
        "confirmed": 0,
        "updated": 0,
        "failed": 0,
        "sonar_used": 0,
        "details": [],
    }

    for src in sources:
        if not src.primary_url:
            continue
        summary["checked"] += 1
        alive, status, final = check_url_alive(src.primary_url)

        detail: dict[str, Any] = {
            "source_key": src.source_key,
            "scraper_name": src.scraper_name,
            "url": src.primary_url,
            "status": status,
            "alive": alive,
        }

        sonar = _verify_official_url_with_sonar(
            source_name=src.source_name,
            source_key=src.source_key,
            current_url=src.primary_url,
            target_field=src.target_field,
            http_alive=alive,
            http_status=status,
            final_url=final if isinstance(final, str) else src.primary_url,
        )
        detail["sonar_used"] = sonar.get("sonar_used", False)
        detail["rationale"] = sonar.get("rationale", "")
        if sonar.get("sonar_used"):
            summary["sonar_used"] += 1

        official_url = sonar.get("official_url")
        action = sonar.get("action", "failed")

        if action == "confirmed" and official_url:
            supabase.table("scraping_sources").update(
                {
                    "url_validated_at": _iso_now(),
                    "url_validation_status": "valid",
                }
            ).eq("id", src.source_id).execute()
            summary["confirmed"] += 1
            detail["action"] = "confirmed"
            summary["details"].append(detail)
            continue

        if action == "updated" and official_url:
            _apply_display_url_update(
                supabase, src, new_url=official_url, detail=detail, summary=summary
            )
            summary["details"].append(detail)
            continue

        # Validation échouée → second passage Sonar dédié à l'affichage
        discovery = _discover_display_url_with_sonar(
            source_name=src.source_name,
            source_key=src.source_key,
            current_url=src.primary_url,
            target_field=src.target_field,
            prior_rationale=detail.get("rationale", ""),
        )
        if discovery.get("sonar_used"):
            summary["sonar_used"] += 1
        detail["discovery_rationale"] = discovery.get("rationale", "")

        discovered_url = discovery.get("official_url")
        if discovery.get("action") == "updated" and discovered_url:
            _apply_display_url_update(
                supabase,
                src,
                new_url=discovered_url,
                detail=detail,
                summary=summary,
                discovery_fallback=True,
            )
            summary["details"].append(detail)
            continue

        supabase.table("scraping_sources").update(
            {
                "url_validation_status": "invalid",
                "url_validated_at": _iso_now(),
            }
        ).eq("id", src.source_id).execute()
        summary["failed"] += 1
        detail["action"] = "failed"
        summary["details"].append(detail)
        logger.warning(
            "Impossible de mettre à jour l'affichage pour %s (%s)",
            src.source_key,
            src.primary_url,
        )

    if refresh_display_links:
        summary["payroll_links"] = refresh_all_payroll_source_links(supabase)

    summary["valid"] = summary["confirmed"]

    logger.info(
        "Validation URLs affichage : %s vérifiées, %s confirmées, %s mises à jour, %s échecs "
        "(%s appels Sonar)",
        summary["checked"],
        summary["confirmed"],
        summary["updated"],
        summary["failed"],
        summary["sonar_used"],
    )
    return summary


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    result = validate_all_official_sources()
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
