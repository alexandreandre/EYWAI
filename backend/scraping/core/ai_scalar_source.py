# backend/scraping/core/ai_scalar_source.py
"""Runner générique pour un AI script mono-source (émet le payload JSON standard)."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from core.ai_extractor import extract_with_web_search, last_citation
from openrouter_client import MODEL_WEB_SEARCH_PRO

OFFICIAL_DEFAULT = [
    "boss.gouv.fr",
    "urssaf.fr",
    "service-public.fr",
    "legifrance.gouv.fr",
    "impots.gouv.fr",
]


def run_ai_scalar_source(
    *,
    source_id: str,
    libelle: str,
    schema: Dict[str, Any],
    schema_name: str,
    task_prompt: str,
    keys: List[str],
    generator: str,
    include_domains: Optional[List[str]] = None,
    label: Optional[str] = None,
) -> None:
    data = extract_with_web_search(
        task_prompt=task_prompt,
        json_schema=schema,
        schema_name=schema_name,
        include_domains=include_domains or OFFICIAL_DEFAULT,
        model=MODEL_WEB_SEARCH_PRO,
    )
    if not data or all(data.get(k) is None for k in keys):
        print(f"ERREUR CRITIQUE: extraction IA {source_id} échouée.", file=sys.stderr)
        sys.exit(1)

    cit = last_citation()
    payload = {
        "id": source_id,
        "type": "bareme",
        "libelle": libelle,
        "valeurs": {k: data.get(k) for k in keys},
        "meta": {
            "source": [
                {
                    "url": cit.get("url", ""),
                    "label": label or libelle,
                    "date_doc": cit.get("date", ""),
                }
            ],
            "scraped_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "generator": generator,
            "method": "ai_web_search",
        },
    }
    print(json.dumps(payload, ensure_ascii=False))
