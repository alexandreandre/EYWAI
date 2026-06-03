#!/usr/bin/env python3
"""Source IA — plafonds Sécurité sociale (recherche web Sonar, témoin URSSAF)."""

import sys
from pathlib import Path

_SCRAPING = Path(__file__).resolve().parent.parent
if str(_SCRAPING) not in sys.path:
    sys.path.insert(0, str(_SCRAPING))

from core.ai_extractor import build_standard_payload, emit_ai_payload_or_exit, extract_with_web_search  # noqa: E402
from core.year_utils import current_year  # noqa: E402

URL = (
    "https://www.urssaf.fr/accueil/outils-documentation/taux-baremes/"
    "plafonds-securite-sociale.html"
)

# Base mensuelle URSSAF pour le plafond horaire (aligné PSS.py).
PSS_MONTHLY_HOURS = 151.67

PLAFOND_KEYS = (
    "annuel",
    "trimestriel",
    "mensuel",
    "quinzaine",
    "hebdomadaire",
    "journalier",
    "horaire",
)

SCHEMA = {
    "type": "object",
    "properties": {k: {"type": ["number", "null"]} for k in PLAFOND_KEYS},
    "required": list(PLAFOND_KEYS),
    "additionalProperties": False,
}


def _to_int(value: object | None) -> int | None:
    if value is None:
        return None
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return None


def _complete_pss_plafonds(raw: dict) -> dict[str, int]:
    """Complète / corrige le barème (formules URSSAF, aligné PSS.py)."""
    annuel = _to_int(raw.get("annuel"))
    mensuel = _to_int(raw.get("mensuel"))
    if annuel is None or mensuel is None:
        raise ValueError("annuel et mensuel obligatoires")

    trimestriel = _to_int(raw.get("trimestriel")) or int(round(annuel / 4))
    quinzaine = _to_int(raw.get("quinzaine")) or (mensuel + 1) // 2
    hebdomadaire = _to_int(raw.get("hebdomadaire")) or int(round(annuel / 52))
    journalier = _to_int(raw.get("journalier")) or int(round(annuel / 218))
    expected_horaire = int(round(mensuel / PSS_MONTHLY_HOURS))
    horaire = _to_int(raw.get("horaire"))
    if horaire is None or abs(horaire - expected_horaire) > 2:
        horaire = expected_horaire

    return {
        "annuel": annuel,
        "trimestriel": trimestriel,
        "mensuel": mensuel,
        "quinzaine": quinzaine,
        "hebdomadaire": hebdomadaire,
        "journalier": journalier,
        "horaire": horaire,
    }


def main() -> None:
    cy = current_year()
    data = extract_with_web_search(
        task_prompt=(
            f"Extrais le barème complet des plafonds de la Sécurité sociale applicables "
            f"en {cy} depuis la page URSSAF plafonds-securite-sociale : annuel, trimestriel, "
            f"mensuel, quinzaine, hebdomadaire, journalier, horaire (montants en euros, entiers). "
            f"Cite en priorité l'URL URSSAF plafonds-securite-sociale.html comme citation_url."
        ),
        json_schema=SCHEMA,
        schema_name="plafonds_ss",
        include_domains=["urssaf.fr", "service-public.gouv.fr", "legifrance.gouv.fr"],
    )
    if not data or data.get("annuel") is None or data.get("mensuel") is None:
        print("ERREUR CRITIQUE: extraction IA plafonds SS échouée.", file=sys.stderr)
        sys.exit(1)

    try:
        sections = _complete_pss_plafonds(data)
    except ValueError:
        print("ERREUR CRITIQUE: extraction IA plafonds SS échouée.", file=sys.stderr)
        sys.exit(1)

    payload = build_standard_payload(
        item_id="plafonds_securite_sociale",
        item_type="bareme_plafond",
        libelle="Plafonds de la Sécurité Sociale",
        sections_or_valeurs=sections,
        generator="PSS/PSS_AI.py",
        source_url=URL,
        source_label="URSSAF plafonds SS (IA web)",
    )
    emit_ai_payload_or_exit(payload, "plafonds_securite_sociale")


if __name__ == "__main__":
    main()
