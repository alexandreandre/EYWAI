#!/usr/bin/env python3
"""Source IA — heures supplémentaires (Sonar + contexte légal officiel)."""

from __future__ import annotations

import importlib.util
import json
import math
import sys
from pathlib import Path

_SCRAPING = Path(__file__).resolve().parent.parent
_DIR = Path(__file__).resolve().parent
if str(_SCRAPING) not in sys.path:
    sys.path.insert(0, str(_SCRAPING))
if str(_DIR) not in sys.path:
    sys.path.insert(0, str(_DIR))

from core.ai_extractor import extract_structured_json  # noqa: E402
from core.official_domains import OFFICIAL_WEB_SEARCH_DOMAINS  # noqa: E402
from core.year_utils import current_year  # noqa: E402

from spec import payload_to_core  # noqa: E402

_HS_FILE = Path(__file__).resolve().parent / "heuressupp.py"
_spec = importlib.util.spec_from_file_location("heuressupp_primary", _HS_FILE)
assert _spec and _spec.loader
hs_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hs_module)

SCHEMA = {
    "type": "object",
    "properties": {
        "majoration_hs_25": {"type": "number"},
        "majoration_hs_50": {"type": "number"},
        "reduction_plafond_legal": {"type": "number"},
        "deduction_effectif_1_19": {"type": "number"},
        "deduction_effectif_20_249": {"type": "number"},
    },
    "required": [
        "majoration_hs_25",
        "majoration_hs_50",
        "reduction_plafond_legal",
        "deduction_effectif_1_19",
        "deduction_effectif_20_249",
    ],
    "additionalProperties": False,
}

OFFICIAL_DOMAINS = list(OFFICIAL_WEB_SEARCH_DOMAINS)


def _core_equal(got: dict, ref: dict, tol: float = 1e-6) -> bool:
    for key in ref:
        a, b = got.get(key), ref.get(key)
        if a is None or b is None:
            return False
        if not math.isclose(float(a), float(b), abs_tol=tol):
            return False
    return True


def _to_payload(core: dict) -> dict:
    return {
        "id": "heures_supp",
        "type": "param_bundle",
        "items": [{"key": k, "value": core[k]} for k in core],
        "meta": {
            "source": [
                {
                    "url": hs_module.URL_MAJORATIONS,
                    "label": "Heures sup. (Sonar + textes officiels)",
                    "date_doc": f"01/01/{current_year()}",
                },
                *hs_module.make_payload()["meta"]["source"][1:],
            ],
            "generator": "scraping/heuressupp/heuressupp_AI.py",
            "method": "ai_web_search",
        },
    }


def extract_core(max_attempts: int = 3) -> dict | None:
    reference = payload_to_core(hs_module.make_payload())
    citation_date = f"01/01/{current_year()}"
    context = hs_module.legal_context_text()

    for attempt in range(1, max_attempts + 1):
        use_web = attempt > 1
        retry = f"\n(Tentative {attempt}/{max_attempts}.)" if attempt > 1 else ""
        prompt = (
            f"Extrais les paramètres de paie heures supplémentaires applicables "
            f"en {current_year()} en France.\n"
            f"Réponds en décimaux : majorations 0.25 = 25 %, montants en euros.\n\n"
            f"--- TEXTES OFFICIELS ---\n{context}\n--- FIN ---\n\n"
            f"Champs : majoration_hs_25, majoration_hs_50, reduction_plafond_legal "
            f"(taux plafond réduction salariale), deduction_effectif_1_19 et "
            f"deduction_effectif_20_249 (€ par heure sup, tranches effectif). "
            f"Recopie les valeurs du texte.{retry}"
        )
        kwargs: dict = {
            "task_prompt": prompt,
            "json_schema": SCHEMA,
            "schema_name": "heures_supp",
            "citation_url": hs_module.URL_REDUCTION,
            "citation_date": citation_date,
            "use_web_search": use_web,
        }
        if use_web:
            kwargs["include_domains"] = OFFICIAL_DOMAINS

        data = extract_structured_json(**kwargs)
        if not data:
            continue
        core = {k: float(data[k]) for k in SCHEMA["required"]}
        if _core_equal(core, reference):
            return core
        print(
            "[heuressupp_AI] Écart vs référentiel légal EYWAI.",
            file=sys.stderr,
        )
    return None


def main() -> None:
    print(f"[heuressupp_AI] Sources : {hs_module.URL_MAJORATIONS}", file=sys.stderr)
    core = extract_core()
    if not core:
        print(
            "ERREUR CRITIQUE: extraction IA heures sup échouée.",
            file=sys.stderr,
        )
        sys.exit(1)
    print(json.dumps(_to_payload(core), ensure_ascii=False))


if __name__ == "__main__":
    main()
