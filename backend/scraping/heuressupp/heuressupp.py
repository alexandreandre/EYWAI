#!/usr/bin/env python3
"""Référentiel légal des taux/montants heures sup. utilisés par le moteur de paie."""

from __future__ import annotations

import json
import sys

# Code du travail L3121-22 / CSS L.241-17 et L.241-18 — valeurs stables au référentiel EYWAI.
URL_MAJORATIONS = (
    "https://travail-emploi.gouv.fr/droit-du-travail/temps-de-travail/"
    "article/les-heures-supplementaires"
)
URL_REDUCTION = "https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000006902239"
URL_DEDUCTION = "https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000038706252"

OFFICIAL_CORE = {
    "majoration_hs_25": 0.25,
    "majoration_hs_50": 0.50,
    "reduction_plafond_legal": 0.1131,
    "deduction_effectif_1_19": 1.5,
    "deduction_effectif_20_249": 0.5,
}


def legal_context_text() -> str:
    """Extraits législatifs pour structuration Sonar (pages souvent anti-bot)."""
    return """
Code du travail — article L3121-22 (majorations heures supplémentaires) :
- Les 8 premières heures supplémentaires : majoration de 25 % (taux 0,25).
- Au-delà de la 8e heure supplémentaire : majoration de 50 % (taux 0,50).

Code de la sécurité sociale — article L241-17 (réduction salariale) :
- Plafond légal de la réduction salariale sur rémunération des heures
  supplémentaires : 11,31 % (taux 0,1131).

Code de la sécurité sociale — article L241-18 (déduction patronale forfaitaire) :
- Employeur de 1 à 19 salariés : 1,50 € par heure supplémentaire.
- Employeur de 20 à 249 salariés : 0,50 € par heure supplémentaire.

Sources :
- Ministère du Travail — heures supplémentaires
- Légifrance LEGIARTI000006902239 (CSS L241-17)
- Légifrance LEGIARTI000038706252 (CSS L241-18)
""".strip()


def make_payload() -> dict:
    return {
        "id": "heures_supp",
        "type": "param_bundle",
        "items": [{"key": k, "value": v} for k, v in OFFICIAL_CORE.items()],
        "meta": {
            "source": [
                {"url": URL_MAJORATIONS, "label": "Ministère du Travail", "date_doc": ""},
                {"url": URL_REDUCTION, "label": "Légifrance CSS L.241-17", "date_doc": ""},
                {"url": URL_DEDUCTION, "label": "Légifrance CSS L.241-18", "date_doc": ""},
            ],
            "generator": "scraping/heuressupp/heuressupp.py",
        },
    }


def main() -> None:
    print(json.dumps(make_payload(), ensure_ascii=False))


if __name__ == "__main__":
    main()
    sys.exit(0)
