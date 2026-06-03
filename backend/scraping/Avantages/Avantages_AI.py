#!/usr/bin/env python3
"""Source IA — avantages en nature (Sonar par bloc, tableaux URSSAF injectés)."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any, Callable

_SCRAPING = Path(__file__).resolve().parent.parent
_DIR = Path(__file__).resolve().parent
if str(_SCRAPING) not in sys.path:
    sys.path.insert(0, str(_SCRAPING))
if str(_DIR) not in sys.path:
    sys.path.insert(0, str(_DIR))

from core.ai_extractor import extract_structured_json  # noqa: E402
from core.year_utils import current_year  # noqa: E402

from _logic import compare_floats, logement_values_equal, normalize_bareme, payload_to_core  # noqa: E402

_AV_FILE = Path(__file__).resolve().parent / "Avantages.py"
_spec = importlib.util.spec_from_file_location("avantages_primary", _AV_FILE)
assert _spec and _spec.loader
av_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(av_module)

URL = av_module.URL_URSSAF

LOGEMENT_ITEM = {
    "type": "object",
    "properties": {
        "remuneration_max": {"type": ["number", "null"]},
        "valeur_1_piece": {"type": "number"},
        "valeur_par_piece": {"type": "number"},
    },
    "required": ["remuneration_max", "valeur_1_piece", "valeur_par_piece"],
    "additionalProperties": False,
}

REPAS_SCHEMA = {
    "type": "object",
    "properties": {"repas": {"type": "number"}},
    "required": ["repas"],
    "additionalProperties": False,
}

TITRE_SCHEMA = {
    "type": "object",
    "properties": {"titre_restaurant": {"type": "number"}},
    "required": ["titre_restaurant"],
    "additionalProperties": False,
}

LOGEMENT_SCHEMA = {
    "type": "object",
    "properties": {
        "logement": {"type": "array", "items": LOGEMENT_ITEM, "minItems": 3},
    },
    "required": ["logement"],
    "additionalProperties": False,
}


def _normalize_bareme_from_ai(lst: list) -> list[dict]:
    out = []
    for obj in lst or []:
        if not isinstance(obj, dict):
            continue
        rem_max = av_module.parse_number(str(obj.get("remuneration_max")))
        v1 = av_module.parse_number(str(obj.get("valeur_1_piece")))
        vpp = av_module.parse_number(str(obj.get("valeur_par_piece")))
        if v1 is None or vpp is None:
            continue
        out.append(
            {
                "remuneration_max_eur": rem_max,
                "valeur_1_piece_eur": v1,
                "valeur_par_piece_suppl_eur": vpp,
            }
        )
    return normalize_bareme(out)


def _align_logement_with_reference(
    got: list[dict], reference: list[dict]
) -> list[dict]:
    """Recopie remuneration_max_eur du parse primary (dernière tranche « au-delà »)."""
    ref_sorted = normalize_bareme(reference)
    got_sorted = normalize_bareme(got)
    if len(ref_sorted) != len(got_sorted):
        return got_sorted
    aligned = []
    for row, ref in zip(got_sorted, ref_sorted):
        aligned.append(
            {
                **row,
                "remuneration_max_eur": ref["remuneration_max_eur"],
            }
        )
    return aligned


def _section_prompt(section: str, table_text: str) -> str:
    return (
        f"Bloc URSSAF « {section} » — avantages en nature {current_year()}.\n"
        f"Extrais EXACTEMENT les montants du tableau ci-dessous (euros).\n\n"
        f"--- TABLEAU OFFICIEL ---\n{table_text}\n--- FIN TABLEAU ---\n\n"
        f"Recopie les chiffres tels quels."
    )


def _extract_block(
    *,
    section: str,
    schema_name: str,
    schema: dict,
    table_text: str,
    post_process: Callable[[dict], Any],
    reference_value: Any,
    matcher: Callable[[Any, Any], bool],
    citation_date: str,
) -> Any | None:
    for attempt in range(1, 4):
        retry = f"\n(Tentative {attempt}/3.)" if attempt > 1 else ""
        data = extract_structured_json(
            task_prompt=_section_prompt(section, table_text) + retry,
            json_schema=schema,
            schema_name=schema_name,
            citation_url=URL,
            citation_date=citation_date,
            use_web_search=False,
        )
        if not data:
            continue
        try:
            parsed = post_process(data)
        except (KeyError, TypeError):
            continue
        if matcher(parsed, reference_value):
            return parsed
        print(
            f"[Avantages_AI] Bloc {section} : écart vs parse URSSAF.",
            file=sys.stderr,
        )
    return None


def build_payload() -> dict | None:
    citation_date = f"01/01/{current_year()}"
    soup = av_module.fetch_soup()
    reference = av_module.scrape_from_soup(soup)
    ref_core = payload_to_core(reference)

    repas = _extract_block(
        section="repas",
        schema_name="avantages_repas",
        schema=REPAS_SCHEMA,
        table_text=av_module.section_table_text(soup, "repas"),
        post_process=lambda d: av_module.parse_number(str(d["repas"])),
        reference_value=ref_core["repas"],
        matcher=lambda a, b: compare_floats(a, b),
        citation_date=citation_date,
    )
    if repas is None:
        return None

    titre = _extract_block(
        section="titre-restaurant",
        schema_name="avantages_titre",
        schema=TITRE_SCHEMA,
        table_text=av_module.section_table_text(soup, "titre"),
        post_process=lambda d: av_module.parse_number(str(d["titre_restaurant"])),
        reference_value=ref_core["titre"],
        matcher=lambda a, b: compare_floats(a, b),
        citation_date=citation_date,
    )
    if titre is None:
        return None

    logement_raw = _extract_block(
        section="logement",
        schema_name="avantages_logement",
        schema=LOGEMENT_SCHEMA,
        table_text=av_module.section_table_text(soup, "logement"),
        post_process=lambda d: _normalize_bareme_from_ai(d.get("logement")),
        reference_value=ref_core["logement"],
        matcher=logement_values_equal,
        citation_date=citation_date,
    )
    if logement_raw is None:
        return None

    logement = _align_logement_with_reference(logement_raw, ref_core["logement"])

    return {
        "id": "avantages_en_nature",
        "type": "param_bundle",
        "items": [
            {"key": "repas_valeur_forfaitaire_eur", "value": repas},
            {"key": "titre_restaurant_exoneration_max_eur", "value": titre},
            {"key": "logement_bareme_forfaitaire", "value": logement},
        ],
        "meta": {
            "source": [
                {
                    "url": URL,
                    "label": "URSSAF avantages (Sonar par bloc, tableaux officiels)",
                    "date_doc": citation_date,
                }
            ],
            "generator": "Avantages/Avantages_AI.py",
            "method": "ai_web_search",
        },
    }


def main() -> None:
    print(f"[Avantages_AI] URL URSSAF : {URL}", file=sys.stderr)
    payload = build_payload()
    if not payload:
        print(
            "ERREUR CRITIQUE: extraction IA avantages échouée (Sonar par bloc).",
            file=sys.stderr,
        )
        sys.exit(1)
    print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
