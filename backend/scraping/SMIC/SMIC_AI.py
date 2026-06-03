#!/usr/bin/env python3
"""Source IA SMIC — Sonar + tableau URSSAF injecté (témoin, pas recherche libre)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_SCRAPING = Path(__file__).resolve().parent.parent
_DIR = Path(__file__).resolve().parent
if str(_SCRAPING) not in sys.path:
    sys.path.insert(0, str(_SCRAPING))
if str(_DIR) not in sys.path:
    sys.path.insert(0, str(_DIR))

from core.ai_extractor import (  # noqa: E402
    build_standard_payload,
    emit_ai_payload_or_exit,
    extract_structured_json,
)
from core.urssaf_parser import smic_monthly_hours  # noqa: E402
from core.validation import normalize_smic_sections  # noqa: E402

from spec import _equal  # noqa: E402

_SMIC_FILE = _DIR / "SMIC.py"
_spec = importlib.util.spec_from_file_location("smic_primary", _SMIC_FILE)
assert _spec and _spec.loader
smic_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(smic_module)

URL = smic_module.URL_URSSAF

SCHEMA = {
    "type": "object",
    "properties": {
        "cas_general": {"type": "number"},
        "jeune_17_ans": {"type": "number"},
        "jeune_moins_17_ans": {"type": "number"},
        "smic_mensuel_brut": {"type": "number"},
    },
    "required": [
        "cas_general",
        "jeune_17_ans",
        "jeune_moins_17_ans",
        "smic_mensuel_brut",
    ],
    "additionalProperties": False,
}


def _iso_to_fr(iso: str) -> str:
    if isinstance(iso, str) and len(iso) >= 10:
        return f"{iso[8:10]}/{iso[5:7]}/{iso[0:4]}"
    return ""


def _reference_core(reference: dict) -> dict:
    return normalize_smic_sections(
        {
            "cas_general": reference["cas_general"],
            "jeune_17_ans": reference["jeune_17_ans"],
            "jeune_moins_17_ans": reference["jeune_moins_17_ans"],
            "smic_mensuel_brut": reference["smic_mensuel_brut"],
            "smic_horaire_brut": reference["cas_general"],
        }
    )


def _sections_from_ai(data: dict, reference: dict) -> dict:
    cas_general = float(data["cas_general"])
    jeune_17 = float(data["jeune_17_ans"])
    jeune_moins_17 = float(data["jeune_moins_17_ans"])
    jeune_17 = min(jeune_17, cas_general)
    jeune_moins_17 = min(jeune_moins_17, jeune_17)
    mensuel = float(data.get("smic_mensuel_brut") or 0)
    if mensuel <= 0:
        mensuel = reference.get("smic_mensuel_brut") or round(
            cas_general * smic_monthly_hours(), 2
        )
    return normalize_smic_sections(
        {
            "cas_general": cas_general,
            "jeune_17_ans": jeune_17,
            "jeune_moins_17_ans": jeune_moins_17,
            "smic_horaire_brut": cas_general,
            "smic_mensuel_brut": mensuel,
            "annee": reference.get("annee"),
        }
    )


def extract_smic(max_attempts: int = 3) -> dict | None:
    soup = smic_module.fetch_soup()
    reference = smic_module.extract_smic_data(soup)
    ref_core = _reference_core(reference)
    table_text = smic_module.applicable_segment_table_text(soup)
    citation_date = _iso_to_fr(str(reference.get("effective_from", ""))) or (
        f"01/01/{reference.get('annee', 2026)}"
    )

    for attempt in range(1, max_attempts + 1):
        use_web = attempt > 1
        retry = f"\n(Tentative {attempt}/{max_attempts}.)" if attempt > 1 else ""
        prompt = (
            f"Extrais le SMIC horaire et mensuel métropole en vigueur depuis le "
            f"tableau URSSAF ci-dessous.\n\n"
            f"--- TABLEAU OFFICIEL ---\n{table_text}\n--- FIN TABLEAU ---\n\n"
            f"Champs : cas_general (Smic horaire brut), jeune_17_ans (17-18 ans), "
            f"jeune_moins_17_ans (<17 ans), smic_mensuel_brut (mensuel). "
            f"Recopie les montants en euros tels quels.{retry}"
        )
        kwargs: dict = {
            "task_prompt": prompt,
            "json_schema": SCHEMA,
            "schema_name": "smic",
            "citation_url": URL,
            "citation_date": citation_date,
            "use_web_search": use_web,
        }
        if use_web:
            kwargs["include_domains"] = [
                "urssaf.fr",
                "service-public.gouv.fr",
                "legifrance.gouv.fr",
            ]

        data = extract_structured_json(**kwargs)
        if not data or data.get("cas_general") is None:
            continue
        sections = _sections_from_ai(data, reference)
        if _equal(sections, ref_core):
            return {**sections, "effective_from": reference.get("effective_from")}
        print(
            "[SMIC_AI] Écart vs parse URSSAF primary.",
            file=sys.stderr,
        )
    return None


def main() -> None:
    print(f"[SMIC_AI] Source : {URL}", file=sys.stderr)
    sections = extract_smic()
    if not sections:
        print("ERREUR CRITIQUE: extraction IA SMIC échouée.", file=sys.stderr)
        sys.exit(1)

    payload = build_standard_payload(
        item_id="smic_horaire",
        item_type="bareme_horaire",
        libelle="SMIC horaire",
        sections_or_valeurs=sections,
        generator="SMIC/SMIC_AI.py",
        source_url=URL,
        source_label="URSSAF SMIC (Sonar + tableau officiel)",
        citation_url=URL,
        citation_date=_iso_to_fr(str(sections.get("effective_from", ""))),
        method="ai_structured",
    )
    emit_ai_payload_or_exit(payload, "smic_horaire")


if __name__ == "__main__":
    main()
