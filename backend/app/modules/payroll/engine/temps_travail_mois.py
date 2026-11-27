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

Le temps payé se mesure sur la durée du contrat : la durée mensuelle du contrat
(durée hebdomadaire × 52 ÷ 12) au générateur des heures, les jours ouvrés de la
période (lundi à vendredi hors fériés) au forfait jours. Il est ensuite ramené à
la durée pleine (`quotite`) : 151,67 h, ou 218 jours au forfait. Un temps partiel
de 28 h touche 80 % de la prime, comme le cabinet la verse (prime × 0,8, vérifié
sur deux bulletins). Au-delà de 35 h, la quotité reste 1 : le cabinet verse la
prime pleine sans majorer les heures sup structurelles (37,5 h : prime pleine,
vérifié au centime) ; question ouverte au regard de l'art. 142 (« supporte […]
les majorations pour heures supplémentaires »). Les heures sup du mois se
rapportent à la durée légale (151,67 h).

Le générateur mesure ce qu'il a retenu et le donne ici (`TempsDuMois`) : la
prime ne relit ni le calendrier ni les pointages.
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
    #: Part de la durée pleine : contrat ÷ 151,67 h (temps partiel), jours du
    #: forfait ÷ 218 (forfait réduit) ; jamais plus de 1.
    quotite: float = 1.0
    #: Durée à laquelle se rapportent les heures sup (151,67 h) ; la référence à défaut.
    reference_heures_sup: float | None = None
    #: Le salaire du mois est retenu en entier (aucun jour prévu travaillé ; « Complément
    #: retenue absence intégrale du mois », ou au forfait « Absence sur tout le mois ») :
    #: le temps non payé couvre alors tout le temps sous contrat, au prorata des absences
    #: qui ne sont pas payées (un arrêt maintenu reste payé).
    mois_entierement_absent: bool = False


@dataclass(frozen=True)
class TempsRetenuResult:
    temps_retenu: float
    reference: float
    ratio: float
    mode: str
    detail: dict[str, Any]


#: Durée pleine : 35 h par semaine, 151,67 h par mois ; 218 jours au forfait
#: (CSS D241-7, IV, comme la réduction générale du forfait réduit).
HEURES_MOIS_DUREE_LEGALE = 151.67
JOURS_FORFAIT_PLEIN = 218.0


def reference_heures_du_contrat(duree_hebdo: float) -> float:
    """Durée mensuelle du contrat : 151,67 h pour 35 h."""
    return round((duree_hebdo * 52) / 12, 2) if duree_hebdo and duree_hebdo > 0 else 151.67


def quotite_heures(duree_hebdo: float) -> float:
    """Temps partiel : contrat ÷ 35 h ; au-delà de 35 h, 1."""
    if not duree_hebdo or duree_hebdo <= 0:
        return 1.0
    return min(float(duree_hebdo) / 35.0, 1.0)


def quotite_forfait(jours_du_forfait: float | None) -> float:
    """Forfait réduit : jours du forfait ÷ 218 ; sans forfait propre, 1."""
    if not jours_du_forfait or jours_du_forfait <= 0:
        return 1.0
    return min(float(jours_du_forfait) / JOURS_FORFAIT_PLEIN, 1.0)


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
    if temps.mois_entierement_absent:
        absences = (
            float(temps.absences_non_payees)
            + float(temps.activite_partielle)
            + sum(float(quantite) for _jour, quantite in temps.jours_arret)
        )
        if absences > 0:
            part_non_payee = (
                float(temps.absences_non_payees) + float(temps.activite_partielle) + arret_non_maintenu
            ) / absences
            sous_contrat = max(float(temps.reference) - float(temps.hors_contrat), 0.0)
            non_paye = float(temps.hors_contrat) + sous_contrat * part_non_payee
    if reference <= 0:
        return TempsRetenuResult(
            temps_retenu=0.0,
            reference=0.0,
            ratio=0.0,
            mode=temps.unite,
            detail={"reason": "reference_nulle"},
        )
    quotite = min(max(float(temps.quotite), 0.0), 1.0)
    present = min(max(reference - non_paye, 0.0), reference)
    heures_sup = float(temps.heures_sup_majorees) if inclure_heures_sup else 0.0
    reference_hs = float(temps.reference_heures_sup or reference)
    ratio = quotite * present / reference + (heures_sup / reference_hs if reference_hs > 0 else 0.0)
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
            "quotite": round(quotite, 6),
            "mois_entierement_absent": bool(temps.mois_entierement_absent),
        },
    )
