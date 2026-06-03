#!/usr/bin/env python3
"""Source IA — catalogue des primes (Sonar confirme les règles de soumission).

Sonar agit comme témoin : pour chaque prime du référentiel EYWAI, il confirme
les booléens soumise_a_cotisations / soumise_a_impot selon la convention
décrite (contexte injecté, pages URSSAF souvent anti-bot). En cas d'écart, le
consensus échoue (cas C) et aucune écriture automatique n'a lieu.
"""

from __future__ import annotations

import copy
import importlib.util
import json
import sys
from pathlib import Path

_SCRAPING = Path(__file__).resolve().parent.parent
_DIR = Path(__file__).resolve().parent
if str(_SCRAPING) not in sys.path:
    sys.path.insert(0, str(_SCRAPING))
if str(_DIR) not in sys.path:
    sys.path.insert(0, str(_DIR))

from core.ai_extractor import extract_structured_json  # noqa: E402
from core.year_utils import current_year  # noqa: E402

_PRIMES_FILE = _DIR / "primes.py"
_spec = importlib.util.spec_from_file_location("primes_primary", _PRIMES_FILE)
assert _spec and _spec.loader
primes_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(primes_module)

CATALOGUE = primes_module.CATALOGUE

ITEM_SCHEMA = {
    "type": "object",
    "properties": {
        "id": {"type": "string"},
        "soumise_a_cotisations": {"type": "boolean"},
        "soumise_a_impot": {"type": "boolean"},
    },
    "required": ["id", "soumise_a_cotisations", "soumise_a_impot"],
    "additionalProperties": False,
}

SCHEMA = {
    "type": "object",
    "properties": {
        "primes": {"type": "array", "items": ITEM_SCHEMA},
    },
    "required": ["primes"],
    "additionalProperties": False,
}


def _reference_signature() -> dict:
    return {
        p["id"]: {
            "soumise_a_impot": p["soumise_a_impot"],
            "soumise_a_cotisations": p["soumise_a_cotisations"],
        }
        for p in CATALOGUE["primes"]
    }


def _ai_signature(data: dict) -> dict:
    out = {}
    for item in data.get("primes", []):
        if not isinstance(item, dict) or not item.get("id"):
            continue
        out[item["id"]] = {
            "soumise_a_impot": bool(item.get("soumise_a_impot")),
            "soumise_a_cotisations": bool(item.get("soumise_a_cotisations")),
        }
    return out


def _build_catalogue_from_signature(sig: dict) -> dict:
    """Recompose le catalogue (libellés + commentaires) avec les booléens Sonar."""
    catalogue = copy.deepcopy(CATALOGUE)
    for prime in catalogue["primes"]:
        confirmed = sig.get(prime["id"])
        if confirmed:
            prime["soumise_a_impot"] = confirmed["soumise_a_impot"]
            prime["soumise_a_cotisations"] = confirmed["soumise_a_cotisations"]
    return catalogue


def _to_payload(catalogue: dict) -> dict:
    return {
        "id": "primes",
        "type": "param_bundle",
        "config_data": catalogue,
        "meta": {
            "source": [
                {
                    "url": primes_module.URL_URSSAF_BAREMES,
                    "label": "Primes — règles de soumission (Sonar + URSSAF)",
                    "date_doc": f"01/01/{current_year()}",
                }
            ],
            "generator": "scraping/primes/primes_AI.py",
            "method": "ai_web_search",
        },
    }


def extract_catalogue(max_attempts: int = 3) -> dict | None:
    reference = _reference_signature()
    context = primes_module.legal_context_text()
    citation_date = f"01/01/{current_year()}"
    ids = ", ".join(reference.keys())

    for attempt in range(1, max_attempts + 1):
        use_web = attempt > 1
        retry = f"\n(Tentative {attempt}/{max_attempts}.)" if attempt > 1 else ""
        prompt = (
            f"Confirme, pour la paie française {current_year()}, les règles de "
            f"soumission de chaque prime ci-dessous.\n\n"
            f"--- RÉFÉRENTIEL À VÉRIFIER ---\n{context}\n--- FIN ---\n\n"
            f"Pour CHAQUE identifiant ({ids}), renvoie soumise_a_cotisations et "
            f"soumise_a_impot (booléens) selon cette convention. Pour les régimes "
            f"conditionnels (PPV, prime de transport, indemnité panier), renvoie la "
            f"valeur « dans les limites d'exonération URSSAF » telle que décrite. "
            f"Recopie les valeurs du référentiel sauf erreur manifeste.{retry}"
        )
        kwargs: dict = {
            "task_prompt": prompt,
            "json_schema": SCHEMA,
            "schema_name": "primes_catalogue",
            "citation_url": primes_module.URL_URSSAF_BAREMES,
            "citation_date": citation_date,
            "use_web_search": use_web,
        }

        data = extract_structured_json(**kwargs)
        if not data:
            continue
        sig = _ai_signature(data)
        if sig == reference:
            return _build_catalogue_from_signature(sig)
        manquants = sorted(set(reference) - set(sig))
        ecarts = sorted(
            k for k in reference if k in sig and sig[k] != reference[k]
        )
        print(
            f"[primes_AI] Écart vs référentiel EYWAI. "
            f"manquants={manquants} écarts={ecarts}",
            file=sys.stderr,
        )
    return None


def main() -> None:
    print(
        f"[primes_AI] Sources : {primes_module.URL_URSSAF_BAREMES}",
        file=sys.stderr,
    )
    catalogue = extract_catalogue()
    if not catalogue:
        print(
            "ERREUR CRITIQUE: extraction IA catalogue primes échouée.",
            file=sys.stderr,
        )
        sys.exit(1)
    print(json.dumps(_to_payload(catalogue), ensure_ascii=False))


if __name__ == "__main__":
    main()
