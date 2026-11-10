"""Rattacher une régularisation à sa période d'origine dans la DSN (page client du 10/11/2026, C1).

Sources ouvertes le 10/11/2026 : cahier technique DSN 2026.1 (2025-12-24),
`docs/audit-maji-2026/sources/dsn-cahier-technique-2026.1.txt` :

- § 2.2.2.2 : « La période de rattachement des cotisations de Sécurité Sociale
  est […] la période d'origine lorsqu'il y a régularisation » ;
- § 2.2.2.5 : une fois passée la date d'exigibilité, les corrections « doivent
  être portées par une DSN mensuelle ultérieure […] Les corrections seront
  valorisées mois civil par mois civil », en approche différentielle ; l'exemple
  déclare, dans la DSN de février, un bloc « Base assujettie - S21.G00.78 » aux
  dates de janvier (78.002 = 01012016, 78.003 = 31012016) ;
- § 2.1.3.6 et 2.1.3.6.2 : un rappel de paie se déclare en approche
  différentielle, « qualifié par le type et la période de rattachement
  initialement déclarée » ;
- S21.G00.51.001 / 51.002 : « Date de début (de fin) de période à laquelle la
  rémunération est rattachée » ;
- S21.G00.78.003 : CCH-15, au plus le dernier jour du mois principal déclaré ;
  CCH-16, même année civile que le début (une base par mois civil le garantit).

Une régularisation saisie sur plusieurs mois (« 07/2026 à 09/2026 », comme la
fenêtre « À partir du bulletin de … Jusqu'au bulletin de … » de l'ancien
logiciel) ne dit pas ce qui revient à chaque mois : Martine la répartit à parts
égales, au centime, le reste sur le dernier mois, et le dit dans l'aperçu de la
DSN. Pour une autre répartition, la gestionnaire saisit une régularisation par
mois.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.modules.dsn_export.domain.contract_map import period_bounds


def mois_entre(debut: str, fin: str | None) -> list[str]:
    """« 2026-07 », « 2026-09 » → [« 2026-07 », « 2026-08 », « 2026-09 »]."""
    annee, mois = (int(x) for x in debut.split("-"))
    dernier = fin or debut
    sortie: list[str] = []
    while True:
        courant = f"{annee:04d}-{mois:02d}"
        sortie.append(courant)
        if courant >= dernier or len(sortie) > 240:
            return sortie
        mois += 1
        if mois > 12:
            annee, mois = annee + 1, 1


def bornes_du_mois(mois: str) -> tuple[str, str]:
    """Premier et dernier jour du mois civil, au format DSN JJMMAAAA."""
    return period_bounds(mois)


def repartir(total: float, parts: int) -> list[float]:
    """Parts égales au centime ; le reste sur la dernière, la somme vaut le total."""
    if parts <= 1:
        return [round(float(total), 2)]
    centimes = int(round(float(total) * 100))
    part = int(centimes / parts)  # tronqué vers zéro, signe gardé
    valeurs = [part] * (parts - 1)
    valeurs.append(centimes - part * (parts - 1))
    return [v / 100 for v in valeurs]


def periode_d_une_cotisation(ligne: Mapping[str, Any]) -> tuple[str, str] | None:
    """La période saisie sur une régularisation de cotisation imprimée, ou None."""
    regul = ligne.get("regularisation")
    if not isinstance(regul, Mapping) or not regul.get("mois_debut"):
        return None
    debut = str(regul["mois_debut"])
    return debut, str(regul.get("mois_fin") or debut)


def periode_d_heures_regularisees(ligne: Mapping[str, Any]) -> tuple[str, str] | None:
    """La période d'origine d'une ligne de régularisation d'heures, ou None."""
    regul = ligne.get("regularisation_heures")
    if not isinstance(regul, Mapping) or not regul.get("mois_origine"):
        return None
    debut = str(regul["mois_origine"])
    return debut, str(regul.get("mois_fin") or debut)


def mois_passes(periode_origine: tuple[str, str], periode_declaree: str) -> tuple[list[str], int]:
    """Les mois d'origine antérieurs au mois déclaré, et le nombre total de mois.

    Les mois égaux ou postérieurs au mois déclaré restent dans sa période :
    ce sont ses propres éléments, pas des régularisations.
    """
    tous = mois_entre(*periode_origine)
    return [m for m in tous if m < periode_declaree], len(tous)


def avis_repartition(salarie: str, libelle: str, mois: list[str]) -> str:
    return (
        f"Salarié {salarie} : la régularisation « {libelle} » couvre {len(mois)} mois ; la DSN "
        "la rattache à chacun de ces mois à parts égales. Si la répartition est autre, "
        "saisissez une régularisation par mois."
    )
