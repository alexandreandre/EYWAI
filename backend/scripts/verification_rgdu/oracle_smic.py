"""SMIC de référence du mois, règle par règle (docs/reference/reduction-generale-2026/regles.md).

La loi (CSS D241-7, IV) part du SMIC d'un mois complet (R-H1, R-H8, R-H9) ; quand le salarié
n'est pas payé tout le mois (absence, arrêt, entrée ou sortie, activité partielle), elle le
corrige du **rapport des salaires** (5e alinéa) : rémunération due pour le mois ÷ rémunération
d'un mois complet, hors éléments non affectés par l'absence. Jamais un calcul en heures.

La base du mois est soit horaire (`duree_mensuelle_contrat`, R-H1 et R-H8), soit celle d'un
forfait jours (`jours_forfait`, R-H9) : les fonctions au rapport et à variante acceptent l'une
ou l'autre, jamais les deux, pour qu'un salarié au forfait ait accès aux mêmes variantes.

Choix de calcul de regles.md appliqués partout :
- n° 1 : base mensuelle 12,02 × 1 820 / 12 arrondie, 1 823,03 € ;
- n° 2 : SMIC du mois arrondi au centime, demi au supérieur, après les proratas et le rapport,
  eux non arrondis ;
- n° 3 : rapport plafonné à 1 ; les heures supplémentaires occasionnelles et les heures
  complémentaires s'ajoutent ensuite, entières, hors plafond.

Points non tranchés (n° 1, maintien subrogé ; n° 4, préavis) : une variante explicite,
obligatoire, jusqu'à la décision d'Alexandre.

Indépendant du moteur : ne rien importer de app/.
"""
from __future__ import annotations

import calendar
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

SMIC_H_2026 = 12.02                  # R-F2 : SMIC de référence figé pour 2026 (décret 2026-509)
DUREE_LEGALE_MENSUELLE = 1820 / 12   # 151,666… h (D241-7, IV, 1er al.)
JOURS_FORFAIT_LEGAL = 218            # D241-7, IV, 3e al.
VARIANTES_MAINTIEN_SUBROGE = ("smic_entier", "rapport_salaires")   # point non tranché n° 1
VARIANTES_PREAVIS = ("hors_rapport", "dans_rapport")                # point non tranché n° 4

_TOLERANCE_DUREE = 0.01   # 151,67 h écrit au contrat vaut la durée légale


def _au_centime(montant: float) -> float:
    """Choix de calcul n° 2 : au centime, demi au supérieur, sur l'écriture décimale du montant."""
    return float(Decimal(repr(montant)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _base_mensuelle(duree_mensuelle_contrat: float, smic_h: float) -> float:
    """R-H1 / R-H8 : SMIC mensuel pour la durée légale, 12,02 × heures du contrat en deçà."""
    if duree_mensuelle_contrat <= 0:
        raise ValueError(f"durée mensuelle du contrat {duree_mensuelle_contrat} h : doit être positive")
    if duree_mensuelle_contrat > DUREE_LEGALE_MENSUELLE + _TOLERANCE_DUREE:
        raise ValueError(
            f"durée mensuelle du contrat {duree_mensuelle_contrat} h au-delà de la durée légale : "
            "la donner hors heures supplémentaires (151,67 h) et passer les heures structurelles "
            "à part (R-H1, D241-7, IV, 2e al.)"
        )
    if duree_mensuelle_contrat >= DUREE_LEGALE_MENSUELLE - _TOLERANCE_DUREE:
        return smic_mensuel(smic_h)
    return smic_h * duree_mensuelle_contrat


def _base_forfait(jours_forfait: float, smic_h: float) -> float:
    """R-H9 : 1 823,03 × min(jours, 218) / 218, non arrondi ; jamais majoré au-delà de 218."""
    if jours_forfait <= 0:
        raise ValueError(f"forfait de {jours_forfait} jours : doit être positif")
    return smic_mensuel(smic_h) * min(jours_forfait, JOURS_FORFAIT_LEGAL) / JOURS_FORFAIT_LEGAL


def _base_du_mois(duree_mensuelle_contrat: float | None, jours_forfait: float | None,
                  heures: float, smic_h: float) -> float:
    """Base horaire (R-H1, R-H8) ou base au forfait jours (R-H9) : exactement l'une des deux.
    Un forfait jours n'a ni heures supplémentaires ni heures complémentaires."""
    if jours_forfait is None:
        if duree_mensuelle_contrat is None:
            raise ValueError("donner la durée mensuelle du contrat ou le forfait jours")
        return _base_mensuelle(duree_mensuelle_contrat, smic_h)
    if duree_mensuelle_contrat is not None:
        raise ValueError(
            "durée mensuelle du contrat et forfait jours s'excluent : passer None pour la durée")
    if heures:
        raise ValueError(f"forfait jours : aucune heure supplémentaire ou complémentaire ({heures} h)")
    return _base_forfait(jours_forfait, smic_h)


def smic_mensuel(smic_h: float = SMIC_H_2026) -> float:
    """R-H1, choix de calcul n° 1 : 12,02 × 1 820 / 12 = 1 823,03 €. R-F2 : 12,02 toute l'année."""
    return _au_centime(smic_h * 1820 / 12)


def smic_mois_complet(duree_mensuelle_contrat: float, heures_sup: float, heures_comp: float,
                      smic_h: float = SMIC_H_2026) -> float:
    """R-H1, R-H8 : mois payé en entier. SMIC mensuel (1 823,03) pour la durée légale, 12,02 ×
    heures mensuelles du contrat pour un temps partiel, plus heures supplémentaires et
    complémentaires payées × 12,02, sans majoration.

    Sert aussi à R-H2 (congés payés pris), R-H4 et R-H5 (paiement intégral du brut, 4e al.),
    R-H6 (férié payé), R-H7 (entrée le 1er, sortie le dernier jour), R-H10 (apprenti : SMIC
    entier même payé sous le SMIC) et R-H12 (les primes n'ajoutent pas de SMIC).

    `duree_mensuelle_contrat` : heures mensuelles du contrat hors heures supplémentaires
    (151,67 pour 35 h comme pour 39 h) ; au-delà de la durée légale, ValueError.
    `heures_sup` : toutes les heures supplémentaires payées du mois, structurelles comprises.
    Forfait jours : `smic_forfait_jours`.
    """
    base = _base_mensuelle(duree_mensuelle_contrat, smic_h)
    return _au_centime(base + (heures_sup + heures_comp) * smic_h)


def smic_forfait_jours(jours_forfait: float, smic_h: float = SMIC_H_2026) -> float:
    """R-H9 : mois complet d'un salarié au forfait jours, 1 823,03 × jours du forfait / 218
    (1 806,30 pour 216 jours) ; à 218 jours et au-delà, SMIC entier, jamais majoré pour des
    jours de repos rachetés.

    Mois complet seulement. Absence (point non tranché n° 8) :
    `smic_au_rapport_des_salaires(None, …, jours_forfait=…)` ; maintien subrogé à 100 %
    (point n° 1) : `smic_maintien_subroge(None, …, variante=…, jours_forfait=…)` ; sortie ou
    entrée en cours de mois : `smic_entree_sortie(None, …, jours_forfait=…)`. Jamais en
    « jours d'absence ÷ (jours du forfait / 12) ».
    """
    return _au_centime(_base_forfait(jours_forfait, smic_h))


def rapport_des_salaires(remuneration_due: float, remuneration_mois_complet: float) -> float:
    """D241-7, IV, 5e al. ; choix de calcul n° 3 : min(1, due / mois complet), non arrondi.

    Rémunération due ≤ 0 : rapport nul (R-A2 b). Mois complet ≤ 0 : ValueError.
    """
    if remuneration_mois_complet <= 0:
        raise ValueError(
            f"rémunération d'un mois complet {remuneration_mois_complet} : doit être positive")
    if remuneration_due <= 0:
        return 0.0
    return min(1.0, remuneration_due / remuneration_mois_complet)


def smic_au_rapport_des_salaires(duree_mensuelle_contrat: float | None, remuneration_due: float,
                                 remuneration_mois_complet: float, *,
                                 jours_forfait: float | None = None,
                                 heures_structurelles: float = 0.0,
                                 heures_sup_occasionnelles: float = 0.0,
                                 heures_comp: float = 0.0,
                                 smic_h: float = SMIC_H_2026) -> float:
    """R-H3, R-H4 (paiement partiel ou nul), R-H5 (maintien partiel ou nul), R-H6 (férié non
    payé, solidarité retenue), R-H7 (via `smic_entree_sortie`), R-H9 (absence au forfait,
    point non tranché n° 8), R-H10 (absences d'un apprenti), R-H11, R-H12.

    SMIC = base × r + heures_structurelles × 12,02 × r
           + (heures_sup_occasionnelles + heures_comp) × 12,02,
    avec r = rapport_des_salaires(due, mois complet). Base : 1 823,03, ou 12,02 × heures du
    contrat à temps partiel (`duree_mensuelle_contrat`), ou 1 823,03 × jours / 218 au forfait
    (`jours_forfait`, avec `duree_mensuelle_contrat=None` et sans heures). Arrondi au centime
    à la fin.

    Les deux montants sont hors éléments non affectés par l'absence (ceux qu'elle ne réduit
    pas de façon strictement proportionnelle : prime non proratisée, prime annuelle, 13e mois,
    heures supplémentaires occasionnelles, frais, indemnité compensatrice de congés payés,
    indemnités de fin de contrat et de rupture) :
    - `remuneration_due` : brut soumis du mois (L242-1) moins ces éléments ; les IJSS
      subrogées n'y sont pas (déduites du brut) ; les IJ complémentaires financées par
      l'employeur y sont ; l'indemnité d'activité partielle n'y est pas ;
    - `remuneration_mois_complet` : brut qu'il aurait eu présent tout le mois, moins les mêmes
      éléments ; il compte la paie des heures structurelles, pas celle des occasionnelles.
    """
    base = _base_du_mois(duree_mensuelle_contrat, jours_forfait,
                         heures_structurelles + heures_sup_occasionnelles + heures_comp, smic_h)
    r = rapport_des_salaires(remuneration_due, remuneration_mois_complet)
    return _au_centime(base * r + heures_structurelles * smic_h * r
                       + (heures_sup_occasionnelles + heures_comp) * smic_h)


def smic_maintien_subroge(duree_mensuelle_contrat: float | None, remuneration_due: float,
                          remuneration_mois_complet: float, *, variante: str,
                          jours_forfait: float | None = None,
                          heures_structurelles: float = 0.0,
                          heures_sup_occasionnelles: float = 0.0,
                          heures_comp: float = 0.0,
                          smic_h: float = SMIC_H_2026) -> float:
    """R-H4, R-H5, point non tranché n° 1 : maintien à 100 % sous déduction des IJSS
    (subrogation), salarié à l'heure ou au forfait jours (`jours_forfait`, R-H9, avec
    `duree_mensuelle_contrat=None`). `variante` obligatoire, sans valeur par défaut :
    - « smic_entier » (lecture de Quadra) : paiement intégral, 4e al., SMIC du mois complet ;
    - « rapport_salaires » : paiement partiel, 5e al., rapport des salaires (brut soumis,
      IJSS déduites, sur le brut d'un mois complet).
    """
    if variante == "smic_entier":
        base = _base_du_mois(duree_mensuelle_contrat, jours_forfait,
                             heures_structurelles + heures_sup_occasionnelles + heures_comp, smic_h)
        return _au_centime(base + (heures_structurelles + heures_sup_occasionnelles + heures_comp) * smic_h)
    if variante == "rapport_salaires":
        return smic_au_rapport_des_salaires(
            duree_mensuelle_contrat, remuneration_due, remuneration_mois_complet,
            jours_forfait=jours_forfait, heures_structurelles=heures_structurelles,
            heures_sup_occasionnelles=heures_sup_occasionnelles,
            heures_comp=heures_comp, smic_h=smic_h)
    raise ValueError(f"variante {variante!r} inconnue : attendu l'une de {VARIANTES_MAINTIEN_SUBROGE}")


def mois_incomplet(annee: int, mois: int, date_entree: date | None = None,
                   date_sortie: date | None = None) -> bool:
    """R-H7 : le mois est-il incomplet par l'entrée ou la sortie ?

    Arrivée le 1er (ou avant le mois) et départ le dernier jour (ou après) : False, le mois
    compte pour un SMIC entier (sous réserve des absences, R-H3). Tout autre jour : True, le
    SMIC du mois suit `smic_entree_sortie`. Aucun jour de contrat dans le mois : ValueError,
    car des sommes rattachées à une période postérieure à la rupture n'ont aucun SMIC et
    sortent du calcul (R-H7, R-A2 d).
    """
    premier = date(annee, mois, 1)
    dernier = date(annee, mois, calendar.monthrange(annee, mois)[1])
    if (date_sortie is not None and date_sortie < premier) or (
            date_entree is not None and date_entree > dernier):
        raise ValueError(f"aucun jour de contrat en {mois:02d}/{annee} : aucun SMIC (R-H7, R-A2 d)")
    return (date_entree is not None and date_entree > premier) or (
        date_sortie is not None and date_sortie < dernier)


def smic_entree_sortie(duree_mensuelle_contrat: float | None, remuneration_due: float,
                       remuneration_mois_complet: float, *,
                       jours_forfait: float | None = None,
                       indemnite_preavis: float = 0.0,
                       variante_preavis: str | None = None,
                       heures_structurelles: float = 0.0,
                       heures_sup_occasionnelles: float = 0.0,
                       heures_comp: float = 0.0,
                       smic_h: float = SMIC_H_2026) -> float:
    """R-H7 : entrée ou sortie un autre jour que le 1er ou le dernier du mois
    (`mois_incomplet` vrai). SMIC du mois × rapport des salaires ; temps partiel : double
    prorata (base 12,02 × heures du contrat, puis rapport) ; forfait jours (R-H9) :
    `jours_forfait`, avec `duree_mensuelle_contrat=None`.

    `remuneration_due` : brut dû pour le mois, sans l'indemnité compensatrice de congés payés,
    l'indemnité de fin de contrat, les autres indemnités de rupture, ni les éléments non
    affectés par l'absence ; **sans** l'indemnité compensatrice de préavis, passée à part.
    `remuneration_mois_complet` : brut d'un mois complet, hors les mêmes éléments.

    Point non tranché n° 4 : si `indemnite_preavis` n'est pas nulle, `variante_preavis` est
    obligatoire ; une valeur inconnue est refusée même sans indemnité.
    - « hors_rapport » : l'indemnité est retirée du rapport, comme une indemnité de rupture ;
    - « dans_rapport » : l'indemnité est ajoutée au seul numérateur (rapport toujours plafonné
      à 1). Cette arithmétique est une lecture de l'implémenteur, pas une règle de regles.md,
      qui dit seulement que la retirer ou non du rapport n'est pas tranché.
    """
    if variante_preavis is not None and variante_preavis not in VARIANTES_PREAVIS:
        raise ValueError(
            f"variante_preavis {variante_preavis!r} inconnue : attendu l'une de {VARIANTES_PREAVIS}")
    if indemnite_preavis:
        if variante_preavis is None:
            raise ValueError(
                f"indemnité de préavis {indemnite_preavis} : variante_preavis obligatoire, "
                f"l'une de {VARIANTES_PREAVIS} (point non tranché n° 4)")
        if variante_preavis == "dans_rapport":
            remuneration_due += indemnite_preavis
    return smic_au_rapport_des_salaires(
        duree_mensuelle_contrat, remuneration_due, remuneration_mois_complet,
        jours_forfait=jours_forfait, heures_structurelles=heures_structurelles,
        heures_sup_occasionnelles=heures_sup_occasionnelles,
        heures_comp=heures_comp, smic_h=smic_h)
