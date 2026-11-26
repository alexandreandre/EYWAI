"""Temps payé du mois, pour le prorata de la prime d'ancienneté (CCN métallurgie).

Règle (enquête du 26/11/2026, textes ouverts sur Légifrance) :

    ratio = 1 − temps non payé ÷ référence  (+ part des heures supplémentaires)

- CCN de la métallurgie du 7 février 2022, art. 142 : « Le montant de la prime
  d'ancienneté varie avec l'horaire de travail. Il supporte donc, le cas échéant,
  les majorations pour heures supplémentaires ou au titre des conventions de
  forfait en jours sur l'année ». La prime suit le temps payé, pas le temps pointé.
- Ne la font baisser que les heures que le bulletin ne paie pas : absence
  injustifiée, non rémunérée ou sans solde ; heures chômées d'activité partielle
  (payées par l'indemnité, R. 5122-18, pas par le salaire) ; arrêt non maintenu ;
  jours hors contrat (entrée ou sortie en cours de mois).
- Restent payés, donc présents : congés payés (L. 3141-24 II), jours fériés
  chômés (L. 3133-3), RTT, formation, école, événements familiaux, arrêt maintenu
  (CCN art. 91.1.2), et le mois court ou long : la mensualisation est
  indépendante du nombre de jours du mois (L. 3242-1).
- Heures supplémentaires : plein mois ÷ référence × heures × (1 + majoration).
  Au forfait en jours, la majoration de 30 % est déjà portée par le plein mois
  (art. 139) : pas de part d'heures supplémentaires.

Référence : la durée mensuelle du contrat (durée hebdomadaire × 52 ÷ 12) au
générateur des heures ; les jours ouvrés de la période (lundi à vendredi hors
fériés) au forfait jours. Le générateur mesure ce qu'il a retenu et le donne ici
(`TempsDuMois`) : la prime ne relit ni le calendrier ni les pointages.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Iterable, Literal, Optional, Set

Unite = Literal["heures", "jours"]


@dataclass(frozen=True)
class TempsDuMois:
    """Ce que le bulletin a retenu du mois, dans l'unité de la référence."""

    unite: Unite
    reference: float
    #: Absence injustifiée, non rémunérée, sans solde.
    absences_non_payees: float = 0.0
    #: Heures chômées d'activité partielle (en jours au forfait : heures ÷ 7).
    activite_partielle: float = 0.0
    #: Temps hors contrat : entrée ou sortie en cours de mois.
    hors_contrat: float = 0.0
    #: Jours d'arrêt retenus : (date, quantité retenue ce jour-là). Le maintien
    #: décide ensuite lesquels restent payés.
    jours_arret: tuple[tuple[date, float], ...] = field(default_factory=tuple)
    #: Σ heures supplémentaires × (1 + majoration) ; 0 au forfait jours.
    heures_sup_majorees: float = 0.0


@dataclass(frozen=True)
class TempsRetenuResult:
    temps_retenu: float
    reference: float
    ratio: float
    mode: str
    detail: dict[str, Any]


def reference_heures_du_contrat(duree_hebdo: float) -> float:
    """Durée mensuelle du contrat : 151,67 h pour 35 h."""
    return round((duree_hebdo * 52) / 12, 2) if duree_hebdo and duree_hebdo > 0 else 151.67


def jours_ouvres_hors_feries(debut: date, fin: date, feries: Iterable[date]) -> list[date]:
    """Les lundis à vendredis de la période, fériés exclus."""
    exclus = set(feries)
    jours = []
    for offset in range((fin - debut).days + 1):
        jour = debut + timedelta(days=offset)
        if jour.weekday() < 5 and jour not in exclus:
            jours.append(jour)
    return jours


def ratio_du_temps_paye(
    temps: TempsDuMois,
    *,
    jours_maintien: Optional[Set[int]] = None,
    maladie_si_maintien: bool = True,
    inclure_heures_sup: bool = True,
    ratio_plafond: float | None = None,
) -> TempsRetenuResult:
    """Ratio de la prime : 1 − temps non payé ÷ référence, plus les heures sup majorées.

    Un jour d'arrêt reste payé quand l'employeur le maintient (`jours_maintien`,
    jours du mois) et que la règle le prévoit (`maladie_si_maintien`).
    """
    jours_maintien = jours_maintien or set()
    reference = float(temps.reference)
    arret_non_maintenu = sum(
        float(quantite)
        for jour, quantite in temps.jours_arret
        if not (maladie_si_maintien and jour.day in jours_maintien)
    )
    non_paye = (
        float(temps.absences_non_payees)
        + float(temps.activite_partielle)
        + float(temps.hors_contrat)
        + arret_non_maintenu
    )
    if reference <= 0:
        return TempsRetenuResult(
            temps_retenu=0.0,
            reference=0.0,
            ratio=0.0,
            mode=temps.unite,
            detail={"reason": "reference_nulle"},
        )
    present = min(max(reference - non_paye, 0.0), reference)
    heures_sup = float(temps.heures_sup_majorees) if inclure_heures_sup else 0.0
    ratio = (present + heures_sup) / reference
    if ratio_plafond is not None:
        ratio = min(ratio, ratio_plafond)
    return TempsRetenuResult(
        temps_retenu=round(present + heures_sup, 2),
        reference=round(reference, 2),
        ratio=round(ratio, 6),
        mode=temps.unite,
        detail={
            "absences_non_payees": round(float(temps.absences_non_payees), 2),
            "activite_partielle": round(float(temps.activite_partielle), 2),
            "hors_contrat": round(float(temps.hors_contrat), 2),
            "arret_non_maintenu": round(arret_non_maintenu, 2),
            "heures_sup_majorees": round(heures_sup, 2),
        },
    )
