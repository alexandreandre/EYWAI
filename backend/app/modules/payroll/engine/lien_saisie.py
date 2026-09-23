"""Le lien entre une ligne de prime du bulletin et la saisie qui l'a produite.

Une prime saisie comme variable du mois (`monthly_inputs`) traverse le
générateur, la répartition soumise / non soumise, puis le calcul du brut. Son
identifiant doit arriver jusqu'à la ligne imprimée : c'est lui qui permet de
corriger ou de retirer cette prime depuis l'écran de modification du bulletin
(spec 2026-09-23). Les primes calculées par le moteur n'en portent pas.
"""

from __future__ import annotations

from typing import Any, Mapping


def lier_a_la_saisie(cible: dict[str, Any], source: Mapping[str, Any]) -> dict[str, Any]:
    """`cible` enrichie du `saisie_id` de `source`, s'il existe."""
    saisie_id = source.get("saisie_id")
    if saisie_id:
        cible["saisie_id"] = str(saisie_id)
    return cible
