"""SMIC que Quadra a implicitement retenu, reconstitué depuis sa réduction cumulée.

Juillet et août n'ont pas de DSN (`dsn_quadra.py`) pour Colorplast ni pour Comitech :
la seule source qui reste, pour ces deux mois, est le bulletin Quadra lui-même
(`quadra_mois.MoisQuadra`), qui imprime la réduction générale appliquée mais jamais
le SMIC qui l'a produite. Ce module retrouve ce SMIC cumulé implicite, mois après
mois, en inversant `oracle.smic_pour_reduction` sur la réduction cumulée que Quadra
a réellement appliquée (somme des `reduction_mois` depuis le début des données
fournies) — puis en dérive le SMIC du mois par différence entre deux SMIC cumulés
consécutifs, exactement comme Quadra dérive la réduction du mois par régularisation
sur un cumul annuel (voir `oracle.reduction_du_mois`).
"""
from __future__ import annotations

from dataclasses import dataclass

from scripts.verification_rgdu.oracle import (
    Parametres, ecart_au_palier, smic_pour_reduction, sous_le_plancher,
)
from scripts.verification_rgdu.quadra_mois import MoisQuadra


@dataclass(frozen=True)
class SmicImplicite:
    """Un mois de SMIC implicite retrouvé depuis la réduction cumulée de Quadra.

    - `smic_mois` : le SMIC du mois (différence de deux SMIC cumulés), `None` si non
      calculable, ou si calculable mais sans point de départ connu (voir la
      docstring de `smic_quadra_par_mois`).
    - `smic_cumule` : le SMIC cumulé, depuis le début des données fournies, dont la
      réduction est la plus proche de celle réellement appliquée par Quadra ce mois
      (voir `oracle.smic_pour_reduction`) ; `None` si non calculable.
    - `ecart_au_palier` : l'écart, en euros, entre la réduction que `smic_cumule`
      donne et celle réellement appliquée par Quadra (voir `oracle.ecart_au_palier`)
      — ce n'est pas une erreur, la réduction n'évolue que par paliers ; `None` si
      non calculable.
    - `sous_le_plancher` : `True` si la réduction cumulée de Quadra tombe dans le
      trou légal entre 0 et Tmin × brut cumulé (voir `oracle.sous_le_plancher`) ;
      toujours `False` si non calculable.
    - `calculable` : `False` si aucun SMIC cumulé n'a pu être retrouvé pour ce mois.
    - `raison` : texte en français expliquant pourquoi, vide si calculable.
    """
    smic_mois: float | None
    smic_cumule: float | None
    ecart_au_palier: float | None
    sous_le_plancher: bool
    calculable: bool
    raison: str


def smic_quadra_par_mois(mois_quadra: list[MoisQuadra], prm: Parametres) -> dict[int, SmicImplicite]:
    """Le SMIC implicite que Quadra a retenu, mois par mois, pour UN salarié.

    Reçoit typiquement tout l'historique de l'année fourni pour ce salarié
    (`quadra_mois.lire_societe`, filtré et trié par clé) — pas seulement juillet et
    août — car le SMIC cumulé implicite d'un mois donné dépend de la réduction
    cumulée depuis le début des données fournies, exactement comme la réduction
    elle-même est une régularisation sur cumul annuel. Les mois qui ont une vraie
    DSN n'ont pas besoin de cette reconstitution ; seuls juillet et août, chez
    Colorplast et Comitech, en dépendent réellement pour le rejeu — mais leur SMIC
    cumulé implicite dépend de tous les mois qui précèdent dans les données passées
    ici.

    Un mois est marqué `calculable=False` (SMIC `None`, `raison` expliquée) dans
    trois cas :

    1. la réduction cumulée jusqu'à ce mois (somme des `reduction_mois` depuis le
       début des données fournies) est nulle ou négative — aucun SMIC cumulé n'y
       correspond (`oracle.smic_pour_reduction` exige une cible strictement
       positive) ;
    2. cette réduction cumulée dépasse le maximum atteignable sur ce brut cumulé —
       `oracle.smic_pour_reduction` lève `ValueError`, interceptée ici ;
    3. le mois précédent DES DONNÉES FOURNIES existait mais n'était pas calculable
       (cas 1 ou 2 ci-dessus) : il n'y a alors plus de SMIC cumulé de départ pour
       isoler le SMIC de CE mois par différence, même si le SMIC cumulé de ce mois
       serait, lui, calculable isolément. La chaîne se réamorce dès que possible :
       le SMIC cumulé de ce mois « non calculable pour cause 3 » est tout de même
       mémorisé en interne, si bien que le mois SUIVANT, s'il est lui-même
       calculable, redevient normal (il dispose alors d'un point de départ).

    Le premier mois des données fournies pour ce salarié (aucun mois avant lui dans
    la liste passée à cette fonction — que ce soit vraiment son premier bulletin ou
    un simple trou de données) est calculable dès que son SMIC cumulé l'est (cas 1
    et 2 ci-dessus écartés), mais son `smic_mois` vaut `None` par défaut : il n'y a
    pas de SMIC cumulé antérieur connu pour distinguer sa propre contribution de ce
    qui aurait pu s'accumuler avant lui. Exception, dans les deux cas où l'on sait
    qu'il n'y avait justement rien avant :

    - c'est janvier (`mois == 1`) : premier mois de l'année, rien ne précède ;
    - le bulletin porte une date d'entrée dans ce mois (`entree` non `None`) : le
      salarié vient d'être embauché, rien ne précède non plus.

    Dans ces deux cas, `smic_mois = smic_cumule` (tout le cumul est le fait de ce
    seul mois). Si ni l'un ni l'autre (ex. le relevé fourni commence en avril sans
    date d'entrée connue ce mois-là — vraisemblablement un trou de données, le
    salarié étant déjà présent avant), `smic_mois` reste `None` : ce cas limite n'a
    pas de réponse fiable depuis les seules données fournies, mieux vaut l'admettre
    que deviner.
    """
    resultat: dict[int, SmicImplicite] = {}
    reduction_cumulee_totale = 0.0
    smic_prec: float | None = None
    premiere_ligne = True

    for m in sorted(mois_quadra, key=lambda x: x.mois):
        reduction_cumulee_totale += m.reduction_mois
        est_premiere, premiere_ligne = premiere_ligne, False

        if reduction_cumulee_totale <= 0:
            resultat[m.mois] = SmicImplicite(
                None, None, None, False, False,
                "réduction cumulée nulle ou négative à ce stade de l'année : "
                "aucun SMIC cumulé n'y correspond",
            )
            smic_prec = None
            continue

        try:
            smic_cumule = round(smic_pour_reduction(m.cumul_bruts, reduction_cumulee_totale, prm), 2)
        except ValueError as exc:
            resultat[m.mois] = SmicImplicite(None, None, None, False, False, str(exc))
            smic_prec = None
            continue

        ecart = ecart_au_palier(m.cumul_bruts, smic_cumule, reduction_cumulee_totale, prm)
        plancher = sous_le_plancher(m.cumul_bruts, reduction_cumulee_totale, prm)

        if smic_prec is not None:
            resultat[m.mois] = SmicImplicite(
                round(smic_cumule - smic_prec, 2), smic_cumule, ecart, plancher, True, "",
            )
        elif est_premiere and (m.mois == 1 or m.entree is not None):
            resultat[m.mois] = SmicImplicite(smic_cumule, smic_cumule, ecart, plancher, True, "")
        elif est_premiere:
            resultat[m.mois] = SmicImplicite(
                None, smic_cumule, ecart, plancher, True,
                "premier mois des données fournies pour ce salarié, ni janvier ni "
                "entrée connue ce mois-là : SMIC du mois non isolable sans point de départ",
            )
        else:
            resultat[m.mois] = SmicImplicite(
                None, None, None, False, False,
                "le mois précédent n'était pas calculable : pas de SMIC cumulé de départ",
            )

        smic_prec = smic_cumule

    return resultat
