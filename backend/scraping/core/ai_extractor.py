"""
Extraction IA avec recherche web OpenRouter (outil openrouter:web_search).

Remplace le pipeline DDGS + fetch page + gpt-4o-mini.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime
from typing import Any
from urllib.parse import urlparse

from core.official_domains import (
    OFFICIAL_URL_SUFFIXES,
    OFFICIAL_WEB_SEARCH_DOMAINS,
    host_is_official,
)
from core.year_utils import current_year

logger = logging.getLogger(__name__)

from openrouter_client import MODEL_WEB_SEARCH  # noqa: E402

# Rétrocompatibilité modules scraping existants
OFFICIAL_DOMAINS = list(OFFICIAL_WEB_SEARCH_DOMAINS)
OFFICIAL_CITATION_DOMAINS = list(OFFICIAL_URL_SUFFIXES)

# Citation de la dernière extraction (un process *_AI.py = une extraction + un payload).
_LAST_CITATION: dict[str, Any] = {}


def _hostname(url: str) -> str:
    try:
        return (urlparse(url.strip()).hostname or "").lower()
    except Exception:
        return ""


def is_official_citation_url(url: str | None) -> bool:
    if not url or not isinstance(url, str):
        return False
    return host_is_official(url)


def _augment_schema_with_citation(json_schema: dict[str, Any]) -> dict[str, Any]:
    """Ajoute citation_url + citation_date au schéma (obligatoires, mode strict)."""
    schema = dict(json_schema)
    props = dict(schema.get("properties", {}))
    props.setdefault("citation_url", {"type": ["string", "null"]})
    props.setdefault("citation_date", {"type": ["string", "null"]})
    schema["properties"] = props
    required = list(schema.get("required", []))
    for key in ("citation_url", "citation_date"):
        if key not in required:
            required.append(key)
    schema["required"] = required
    return schema


def last_citation() -> dict[str, Any]:
    """Citation (url + date) de la dernière extraction IA réussie."""
    return dict(_LAST_CITATION)


def extract_with_web_search(
    *,
    task_prompt: str,
    json_schema: dict[str, Any],
    schema_name: str = "extraction",
    include_domains: list[str] | None = None,
    model: str = MODEL_WEB_SEARCH,
    require_citation: bool = True,
) -> dict[str, Any] | None:
    """
    Interroge un modèle avec recherche web et sortie JSON strictement schématisée.

    Citation imposée : le schéma exige citation_url + citation_date. Si la citation
    est absente, non datée ou non officielle, l'extraction est REJETÉE (retourne
    None) — l'IA reste un témoin / rapporteur de preuve, jamais une vérité aveugle.
    """
    global _LAST_CITATION
    from openrouter_client import chat_completions_create, require_api_key

    try:
        require_api_key()
    except ValueError:
        print("ERREUR: OPENROUTER_API_KEY manquante.", file=sys.stderr)
        return None

    today = datetime.now().strftime("%d/%m/%Y")
    year = current_year()
    domains = include_domains or OFFICIAL_DOMAINS
    domain_hint = ", ".join(domains[:8])

    effective_schema = (
        _augment_schema_with_citation(json_schema) if require_citation else json_schema
    )

    system = (
        "Tu es un assistant expert en réglementation sociale et paie française. "
        "Utilise uniquement des sources officielles récentes. "
        f"Priorise les domaines : {domain_hint}. "
        "Réponds UNIQUEMENT en JSON valide conforme au schéma fourni. "
        "Ne invente pas de valeurs : si une donnée est introuvable, mets null."
    )
    citation_hint = ""
    if require_citation:
        citation_hint = (
            "\nIndique OBLIGATOIREMENT citation_url (l'URL exacte de la page "
            "officielle effectivement utilisée) et citation_date (date du document "
            "ou de mise à jour, format JJ/MM/AAAA)."
        )
    user = f"""Date du jour : {today}.
Année réglementaire cible : {year}.

{task_prompt}

Ne cite pas d'exemples chiffrés fictifs. Extrais les valeurs applicables en {year}.{citation_hint}"""

    plugins = [
        {
            "id": "web",
            "max_results": 5,
            "include_domains": domains,
        }
    ]

    try:
        resp = chat_completions_create(
            model=model,
            temperature=0,
            max_tokens=4096,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": schema_name,
                    "strict": True,
                    "schema": effective_schema,
                },
            },
            extra_body={"plugins": plugins},
        )
        raw = (resp.choices[0].message.content or "").strip()
        data = json.loads(raw)
    except Exception as e:
        logger.error("Extraction IA web_search échouée: %s", e)
        print(f"ERREUR extraction IA : {e}", file=sys.stderr)
        return None

    if not isinstance(data, dict):
        return None

    citation_url = data.pop("citation_url", None)
    citation_date = data.pop("citation_date", None)

    if require_citation:
        citation_url = (
            citation_url.strip()
            if isinstance(citation_url, str) and citation_url.strip()
            else None
        )
        citation_date = (
            str(citation_date).strip()
            if citation_date is not None and str(citation_date).strip()
            else None
        )
        if is_official_citation_url(citation_url) and not citation_date:
            # Sonar renvoie souvent l'URL officielle sans date (ex. agirc-arrco.fr).
            citation_date = f"01/01/{year}"
        if not is_official_citation_url(citation_url) or not citation_date:
            logger.error(
                "Citation IA absente/non officielle — extraction rejetée (url=%s, date=%s)",
                citation_url,
                citation_date,
            )
            print(
                "ERREUR: citation officielle datée manquante — extraction IA rejetée.",
                file=sys.stderr,
            )
            return None

    _LAST_CITATION = {"url": citation_url, "date": citation_date}
    return data


def extract_structured_json(
    *,
    task_prompt: str,
    json_schema: dict[str, Any],
    schema_name: str = "extraction",
    citation_url: str,
    citation_date: str,
    model: str = MODEL_WEB_SEARCH,
    use_web_search: bool = False,
    include_domains: list[str] | None = None,
) -> dict[str, Any] | None:
    """
    Extraction JSON structurée (modèle Sonar) avec citation imposée en entrée.

    use_web_search=False : le prompt doit contenir le contexte (ex. tableau BOFIP).
    """
    global _LAST_CITATION
    from openrouter_client import chat_completions_create, require_api_key

    if not is_official_citation_url(citation_url) or not str(citation_date).strip():
        logger.error("extract_structured_json : citation invalide")
        return None

    try:
        require_api_key()
    except ValueError:
        print("ERREUR: OPENROUTER_API_KEY manquante.", file=sys.stderr)
        return None

    today = datetime.now().strftime("%d/%m/%Y")
    system = (
        "Tu es un assistant expert en réglementation fiscale et paie française. "
        "Réponds UNIQUEMENT en JSON valide conforme au schéma fourni. "
        "Ne invente pas de valeurs : recopie exactement les chiffres du contexte."
    )
    user = f"Date du jour : {today}.\n\n{task_prompt}"

    request_kwargs: dict[str, Any] = {
        "model": model,
        "temperature": 0,
        "max_tokens": 4096,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": schema_name,
                "strict": True,
                "schema": json_schema,
            },
        },
    }
    if use_web_search:
        request_kwargs["extra_body"] = {
            "plugins": [
                {
                    "id": "web",
                    "max_results": 5,
                    "include_domains": include_domains or OFFICIAL_DOMAINS,
                }
            ]
        }

    try:
        resp = chat_completions_create(**request_kwargs)
        raw = (resp.choices[0].message.content or "").strip()
        data = json.loads(raw)
    except Exception as e:
        logger.error("extract_structured_json échouée: %s", e)
        print(f"ERREUR extraction IA : {e}", file=sys.stderr)
        return None

    if not isinstance(data, dict):
        return None

    _LAST_CITATION = {"url": citation_url, "date": citation_date}
    return data


def build_standard_payload(
    *,
    item_id: str,
    item_type: str,
    libelle: str,
    sections_or_valeurs: dict,
    generator: str,
    source_url: str,
    source_label: str,
    use_valeurs: bool = False,
    citation_url: str | None = None,
    citation_date: str | None = None,
    method: str = "ai_web_search",
) -> dict[str, Any] | None:
    from datetime import datetime, timezone

    # Citation obligatoire : URL officielle + date non vide (plan Phase 2).
    last = last_citation()
    cited_url = citation_url or last.get("url") or source_url
    cited_date = citation_date or last.get("date") or ""
    if not is_official_citation_url(cited_url) or not cited_date:
        logger.error(
            "build_standard_payload rejeté : citation officielle datée manquante "
            "(url=%s, date=%s)",
            cited_url,
            cited_date,
        )
        return None

    scraped_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    body: dict[str, Any] = {
        "id": item_id,
        "type": item_type,
        "libelle": libelle,
        "meta": {
            "source": [
                {"url": cited_url, "label": source_label, "date_doc": cited_date}
            ],
            "scraped_at": scraped_at,
            "generator": generator,
            "method": method,
        },
    }
    if use_valeurs:
        body["valeurs"] = sections_or_valeurs
    else:
        body["sections"] = sections_or_valeurs
    return body


def emit_ai_payload_or_exit(payload: dict[str, Any] | None, item_id: str) -> None:
    """Affiche le payload JSON ou quitte avec code 1 si citation invalide."""
    if payload is None:
        print(
            f"ERREUR CRITIQUE: payload IA {item_id} sans citation officielle datée.",
            file=sys.stderr,
        )
        sys.exit(1)
    print(json.dumps(payload, ensure_ascii=False))
