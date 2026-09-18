"""Génération en bac à sable : le passé vient de l'appelant, rien n'est écrit.

Un rejeu d'audit — Colorplast, janvier à juin rejoués à la régulière pour
contrôler la paie de Gaëlle — ne doit jamais écrire dans la chaîne de paie :
ni `payslips`, ni `employee_schedules.cumuls`, ni le storage, ni les compteurs
de modulation, de CET ou de repos. C'est ce qui a fait casser janvier trois
fois, et la bascule de reprise (`app/shared/reprise_paie.py`) interdit
désormais de recalculer ces mois pour de bon.

Le bac à sable est l'espace de l'audit : le générateur reçoit ses cumuls
précédents en mémoire, calcule le bulletin exactement comme d'habitude, et le
rend à l'appelant avec ses nouveaux cumuls au lieu de les persister. C'est
l'appelant qui chaîne ses mois.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass


@dataclass(frozen=True)
class BacASable:
    """Ce que l'appelant fournit à la place de la base.

    `cumuls_precedents` : le bloc `employee_schedules.cumuls` du mois d'avant,
    tel que le générateur l'aurait lu ; None = départ à zéro, comme pour le
    tout premier bulletin d'un salarié.
    """

    cumuls_precedents: dict | None = None


def cumuls_de_depart(bac: BacASable, year: int) -> dict:
    """Les cumuls que le générateur écrit dans son fichier du mois précédent."""
    if bac.cumuls_precedents is None:
        return {
            "periode": {"annee_en_cours": year, "dernier_mois_calcule": 0},
            "cumuls": {
                "brut_total": 0.0,
                "heures_remunerees": 0.0,
                "reduction_generale_patronale": 0.0,
                "net_imposable": 0.0,
                "impot_preleve_a_la_source": 0.0,
                "heures_supplementaires_remunerees": 0.0,
            },
        }
    # Copie : le générateur enrichit ce dictionnaire, l'appelant garde sa chaîne.
    return copy.deepcopy(bac.cumuls_precedents)
