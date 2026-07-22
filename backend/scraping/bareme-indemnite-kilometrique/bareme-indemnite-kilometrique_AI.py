#!/usr/bin/env python3
"""Source IA — barème indemnité kilométrique (recherche web)."""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

_SCRAPING = Path(__file__).resolve().parent.parent
if str(_SCRAPING) not in sys.path:
    sys.path.insert(0, str(_SCRAPING))

from core.ai_extractor import extract_with_web_search  # noqa: E402
from core.year_utils import current_year  # noqa: E402
from openrouter_client import MODEL_WEB_SEARCH_PRO  # noqa: E402

URL = "https://bofip.impots.gouv.fr/bofip/"

OFFICIAL = [
    "bofip.impots.gouv.fr",
    "urssaf.fr",
    "service-public.fr",
    "legifrance.gouv.fr",
]

FORMULE_SCHEMA = {
    "type": "object",
    "properties": {
        "segment": {"type": "integer"},
        "a": {"type": ["number", "null"]},
        "b": {"type": ["number", "null"]},
    },
    "required": ["segment", "a", "b"],
    "additionalProperties": False,
}

TRANCHE_SCHEMA = {
    "type": "object",
    "properties": {
        "cv_min": {"type": ["integer", "null"]},
        "cv_max": {"type": ["integer", "null"]},
        "formules": {"type": "array", "items": FORMULE_SCHEMA},
    },
    "required": ["cv_min", "cv_max", "formules"],
    "additionalProperties": False,
}

SCHEMA = {
    "type": "object",
    "properties": {
        "voitures": {"type": "array", "items": TRANCHE_SCHEMA},
        "motocyclettes": {"type": "array", "items": TRANCHE_SCHEMA},
        "cyclomoteurs": {"type": "array", "items": TRANCHE_SCHEMA},
    },
    "required": ["voitures", "motocyclettes", "cyclomoteurs"],
    "additionalProperties": False,
}


def validate_payload(data: dict) -> bool:
    try:
        if not isinstance(data.get("voitures"), list) or len(data["voitures"]) != 5:
            return False
        for tr in data["voitures"]:
            if len(tr.get("formules", [])) != 3:
                return False
        if not isinstance(data.get("motocyclettes"), list) or len(data["motocyclettes"]) != 3:
            return False
        for tr in data["motocyclettes"]:
            if len(tr.get("formules", [])) != 3:
                return False
        if not isinstance(data.get("cyclomoteurs"), list) or len(data["cyclomoteurs"]) != 1:
            return False
        if len(data["cyclomoteurs"][0].get("formules", [])) != 3:
            return False
        return True
    except Exception:
        return False


def _round_formules(data: dict) -> dict:
    for bloc in ("voitures", "motocyclettes", "cyclomoteurs"):
        for tr in data[bloc]:
            for f in tr["formules"]:
                if f["a"] is not None:
                    f["a"] = round(float(f["a"]), 3)
                if f["b"] is not None:
                    f["b"] = round(float(f["b"]), 3)
    return data


def main() -> None:
    cy = current_year()
    data = extract_with_web_search(
        task_prompt=(
            f"Extrais le barème kilométrique fiscal officiel EN VIGUEUR pour la "
            f"déclaration {cy} (revenus {cy - 1}), tel que publié au BOFiP / "
            f"service-public.fr. Utilise IMPÉRATIVEMENT la dernière version "
            f"revalorisée du barème ; n'utilise JAMAIS un barème d'une année "
            f"antérieure (les coefficients d'avant 2023 sont périmés). "
            f"Voitures, motocyclettes et cyclomoteurs. "
            f"Chaque formule : coût = a × d + b (a en €/km, b en €, d en km). "
            f"Voitures : 5 tranches de puissance (≤3 CV, 4 CV, 5 CV, 6 CV, ≥7 CV), "
            f"segments d≤5000 / 5001–20000 / >20000. "
            f"Motos : 3 tranches CV, segments d≤3000 / 3001–6000 / >6000. "
            f"Cyclomoteurs : 1 tranche, mêmes segments que motos. "
            f"Reporte les coefficients EXACTEMENT tels qu'ils figurent dans le "
            f"barème officiel le plus récent."
        ),
        json_schema=SCHEMA,
        schema_name="bareme_km",
        include_domains=OFFICIAL,
        model=MODEL_WEB_SEARCH_PRO,
    )
    if not data or not validate_payload(data):
        print("ERREUR CRITIQUE: extraction IA barème km échouée.", file=sys.stderr)
        sys.exit(1)

    ai_data = _round_formules(data)
    veh = {
        "voitures": {
            "base": "distance_km",
            "segments": [
                {"d_min": 0, "d_max": 5000},
                {"d_min": 5001, "d_max": 20000},
                {"d_min": 20001, "d_max": None},
            ],
            "tranches_cv": ai_data["voitures"],
        },
        "motocyclettes": {
            "base": "distance_km",
            "segments": [
                {"d_min": 0, "d_max": 3000},
                {"d_min": 3001, "d_max": 6000},
                {"d_min": 6001, "d_max": None},
            ],
            "tranches_cv": ai_data["motocyclettes"],
        },
        "cyclomoteurs": {
            "base": "distance_km",
            "segments": [
                {"d_min": 0, "d_max": 3000},
                {"d_min": 3001, "d_max": 6000},
                {"d_min": 6001, "d_max": None},
            ],
            "tranches_cv": ai_data["cyclomoteurs"],
        },
    }
    payload = {
        "id": "baremes_km",
        "type": "barème_kilométrique",
        "libelle": f"Barème kilométrique {cy} (IA web)",
        "annee": cy,
        "vehicules": veh,
        "meta": {
            "source": [{"url": URL, "label": "BOFiP barème km (IA web)", "date_doc": ""}],
            "scraped_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "generator": "bareme-indemnite-kilometrique/bareme-indemnite-kilometrique_AI.py",
            "method": "ai_web_search",
        },
    }
    print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
