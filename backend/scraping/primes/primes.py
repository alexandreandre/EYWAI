#!/usr/bin/env python3
"""Catalogue de référence des primes (règles de soumission paie).

Catalogue curaté des primes et indemnités RH les plus courantes en paie
française, avec leurs règles de soumission aux cotisations sociales et à
l'impôt sur le revenu. Ce n'est pas la totalité des libellés possibles
(usages, CCN…), mais le socle classique utilisé par le moteur de paie.

Convention des booléens :
- soumise_a_cotisations / soumise_a_impot décrivent le régime PAR DÉFAUT.
- Pour les primes à régime conditionnel (PPV, transport, panier), la valeur
  retenue est celle « dans les limites d'exonération URSSAF » ; le moteur de
  paie ré-applique les conditions fines (effectif, plafonds) au calcul.
"""

from __future__ import annotations

import json
import sys

# Sources officielles de référence (témoins, pas vérité aveugle).
URL_URSSAF_BAREMES = "https://www.urssaf.fr/accueil/outils-documentation/taux-baremes.html"
URL_PPV = (
    "https://www.urssaf.fr/accueil/employeur/beneficier-mesure/"
    "prime-partage-valeur.html"
)
URL_FRAIS_PRO = (
    "https://www.urssaf.fr/accueil/outils-documentation/taux-baremes/"
    "frais-professionnels.html"
)

CATALOGUE = {
    "primes": [
        {
            "id": "prime_exceptionnelle",
            "libelle": "Prime exceptionnelle",
            "soumise_a_impot": True,
            "soumise_a_cotisations": True,
        },
        {
            "id": "prime_partage_valeur",
            "libelle": "Prime de partage de la valeur (PPV)",
            "soumise_a_impot": False,
            "soumise_a_cotisations": False,
            "_commentaire": (
                "Exonération sous conditions de montant et de rémunération. "
                "L'assujettissement à l'impôt dépend de l'effectif : exonérée d'impôt "
                "si l'entreprise compte moins de 50 salariés, soumise à l'impôt à partir "
                "de 50 salariés (règle appliquée automatiquement en paie)."
            ),
        },
        {
            "id": "prime_anciennete",
            "libelle": "Prime d'ancienneté",
            "soumise_a_impot": True,
            "soumise_a_cotisations": True,
        },
        {
            "id": "prime_13eme_mois",
            "libelle": "Prime de 13e mois",
            "soumise_a_impot": True,
            "soumise_a_cotisations": True,
        },
        {
            "id": "prime_vacances",
            "libelle": "Prime de vacances",
            "soumise_a_impot": True,
            "soumise_a_cotisations": True,
        },
        {
            "id": "prime_objectifs",
            "libelle": "Prime d'objectifs / de performance",
            "soumise_a_impot": True,
            "soumise_a_cotisations": True,
        },
        {
            "id": "prime_assiduite",
            "libelle": "Prime d'assiduité",
            "soumise_a_impot": True,
            "soumise_a_cotisations": True,
        },
        {
            "id": "prime_nuit",
            "libelle": "Prime de nuit",
            "soumise_a_impot": True,
            "soumise_a_cotisations": True,
        },
        {
            "id": "prime_risque",
            "libelle": "Prime de risque / de sujétion",
            "soumise_a_impot": True,
            "soumise_a_cotisations": True,
        },
        {
            "id": "prime_cooptation",
            "libelle": "Prime de cooptation",
            "soumise_a_impot": True,
            "soumise_a_cotisations": True,
        },
        {
            "id": "prime_transport",
            "libelle": "Prime de transport (carburant / frais de trajet)",
            "soumise_a_impot": False,
            "soumise_a_cotisations": False,
            "_commentaire": (
                "Exonérée dans les limites fixées par l'URSSAF (prise en charge "
                "facultative des frais de carburant / alimentation des véhicules). "
                "La fraction qui dépasse le plafond annuel est réintégrée."
            ),
        },
        {
            "id": "indemnite_panier_repas",
            "libelle": "Indemnité panier repas",
            "soumise_a_impot": False,
            "soumise_a_cotisations": False,
            "_commentaire": (
                "Exonération dans les limites fixées par l'URSSAF (voir barème Frais professionnels)."
            ),
        },
    ],
    "_commentaire": (
        "Catalogue des primes, indemnités et gratifications les plus courantes "
        "avec leurs règles de soumission aux cotisations sociales et à l'impôt "
        "sur le revenu."
    ),
}


def legal_context_text() -> str:
    """Règles de soumission injectées comme contexte pour la validation Sonar.

    Les pages URSSAF étant souvent anti-bot, on fournit le référentiel attendu
    (convention EYWAI) que Sonar doit confirmer prime par prime.
    """
    lignes = []
    for prime in CATALOGUE["primes"]:
        cotis = "OUI" if prime["soumise_a_cotisations"] else "NON"
        impot = "OUI" if prime["soumise_a_impot"] else "NON"
        note = prime.get("_commentaire", "")
        note = f" — {note}" if note else ""
        lignes.append(
            f"- {prime['id']} ({prime['libelle']}) : "
            f"soumise aux cotisations = {cotis}, soumise à l'impôt = {impot}.{note}"
        )
    return (
        "Règles de soumission des primes et indemnités (paie française) :\n"
        + "\n".join(lignes)
        + "\n\nRappels :\n"
        "- Une prime qui constitue un complément de rémunération est soumise aux "
        "cotisations sociales ET à l'impôt sur le revenu.\n"
        "- Les exonérations (PPV, prime de transport, indemnité panier) ne valent "
        "que dans les limites et conditions fixées par l'URSSAF."
    )


def make_payload() -> dict:
    return {
        "id": "primes",
        "type": "param_bundle",
        "config_data": CATALOGUE,
        "meta": {
            "source": [
                {
                    "url": URL_URSSAF_BAREMES,
                    "label": "URSSAF — barèmes et exonérations",
                    "date_doc": "",
                }
            ],
            "generator": "scraping/primes/primes.py",
        },
    }


def main() -> None:
    print(json.dumps(make_payload(), ensure_ascii=False))


if __name__ == "__main__":
    main()
    sys.exit(0)
