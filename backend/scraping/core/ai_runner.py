"""Runners communs pour les scripts *_AI.py (recherche web)."""

from __future__ import annotations

import json
import sys
from typing import Any

from core.ai_extractor import build_standard_payload, extract_with_web_search


def _percent_schema(name: str = "taux") -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            name: {"type": ["number", "null"]},
        },
        "required": [name],
        "additionalProperties": False,
    }


def run_patronal_percent_ai(
    *,
    item_id: str,
    libelle: str,
    task_prompt: str,
    source_url: str,
    source_label: str,
    generator: str,
    schema_key: str = "patronal_percent",
    domains: list[str] | None = None,
) -> None:
    schema = _percent_schema(schema_key)
    data = extract_with_web_search(
        task_prompt=task_prompt,
        json_schema=schema,
        schema_name=item_id,
        include_domains=domains,
    )
    if not data or data.get(schema_key) is None:
        print(f"ERREUR CRITIQUE: extraction IA {item_id} échouée.", file=sys.stderr)
        sys.exit(1)
    rate = round(float(data[schema_key]) / 100.0, 6)
    payload = build_standard_payload(
        item_id=item_id,
        item_type="cotisation",
        libelle=libelle,
        sections_or_valeurs={"salarial": None, "patronal": rate},
        generator=generator,
        source_url=source_url,
        source_label=source_label,
        use_valeurs=True,
    )
    if payload is None:
        print(f"ERREUR CRITIQUE: payload IA {item_id} sans citation valide.", file=sys.stderr)
        sys.exit(1)
    payload["base"] = "brut"
    print(json.dumps(payload, ensure_ascii=False))


def run_sections_ai(
    *,
    item_id: str,
    item_type: str,
    libelle: str,
    task_prompt: str,
    json_schema: dict[str, Any],
    schema_name: str,
    source_url: str,
    source_label: str,
    generator: str,
    map_result: callable,
    domains: list[str] | None = None,
) -> None:
    data = extract_with_web_search(
        task_prompt=task_prompt,
        json_schema=json_schema,
        schema_name=schema_name,
        include_domains=domains,
    )
    if not data:
        print(f"ERREUR CRITIQUE: extraction IA {item_id} échouée.", file=sys.stderr)
        sys.exit(1)
    sections = map_result(data)
    payload = build_standard_payload(
        item_id=item_id,
        item_type=item_type,
        libelle=libelle,
        sections_or_valeurs=sections,
        generator=generator,
        source_url=source_url,
        source_label=source_label,
        use_valeurs=False,
    )
    if payload is None:
        print(f"ERREUR CRITIQUE: payload IA {item_id} sans citation valide.", file=sys.stderr)
        sys.exit(1)
    print(json.dumps(payload, ensure_ascii=False))
