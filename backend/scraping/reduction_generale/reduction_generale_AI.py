#!/usr/bin/env python3
"""Source IA — paramètres RGDU (recherche web sourcée)."""
import sys
from pathlib import Path

_SCRAPING = Path(__file__).resolve().parent.parent
if str(_SCRAPING) not in sys.path:
    sys.path.insert(0, str(_SCRAPING))

from core.ai_scalar_source import run_ai_scalar_source  # noqa: E402

SCHEMA = {
    "type": "object",
    "properties": {
        "tmin": {"type": ["number", "null"]},
        "p": {"type": ["number", "null"]},
        "point_sortie_smic": {"type": ["number", "null"]},
        "tdelta_fnal_moins_50": {"type": ["number", "null"]},
        "tdelta_fnal_50_et_plus": {"type": ["number", "null"]},
    },
    "required": [
        "tmin",
        "p",
        "point_sortie_smic",
        "tdelta_fnal_moins_50",
        "tdelta_fnal_50_et_plus",
    ],
    "additionalProperties": False,
}

if __name__ == "__main__":
    run_ai_scalar_source(
        source_id="reduction_generale",
        libelle="Paramètres RGDU (réduction générale dégressive)",
        schema=SCHEMA,
        schema_name="reduction_generale",
        keys=[
            "tmin",
            "p",
            "point_sortie_smic",
            "tdelta_fnal_moins_50",
            "tdelta_fnal_50_et_plus",
        ],
        generator="reduction_generale/reduction_generale_AI.py",
        task_prompt=(
            "Réduction générale dégressive des cotisations patronales (RGDU) "
            "en France, année courante : "
            "1) coefficient maximal T pour employeurs de moins de 50 "
            "salariés (FNAL 0,10 %), champ tdelta_fnal_moins_50, "
            "en FRACTION (ex : 0.3193). "
            "2) coefficient maximal T pour employeurs de 50 salariés et plus "
            "(FNAL 0,50 %), champ tdelta_fnal_50_et_plus, "
            "en FRACTION (ex : 0.3233). "
            "3) exposant de dégressivité P, champ p. "
            "4) point de sortie en MULTIPLE du SMIC, champ "
            "point_sortie_smic (ex : 3.0). "
            "5) taux plancher Tmin, champ tmin. "
            "Sources officielles (BOSS, URSSAF)."
        ),
        label="BOSS/URSSAF — paramètres RGDU (IA web)",
    )
