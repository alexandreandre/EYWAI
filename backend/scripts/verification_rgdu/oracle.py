"""Formule de la réduction générale 2026 (RGDU), écrite depuis les textes (regles.md, R-F1).

Indépendante du moteur : ne rien importer de app/.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import ceil, floor


@dataclass(frozen=True)
class Parametres:
    tmin: float = 0.02
    tdelta: float = 0.3781        # moins de 50 salariés ; 0.3821 à partir de 50
    p: float = 1.75
    point_sortie: float = 3.0     # en SMIC

    @property
    def tmax(self) -> float:
        return round(self.tmin + self.tdelta, 4)


def coefficient(brut_cumule: float, smic_cumule: float, prm: Parametres) -> float:
    if brut_cumule <= 0 or smic_cumule <= 0:
        return 0.0
    if round(brut_cumule, 2) >= round(prm.point_sortie * smic_cumule, 2):
        return 0.0
    crochet = 0.5 * (prm.point_sortie * smic_cumule / brut_cumule - 1)
    return round(min(prm.tmin + prm.tdelta * crochet ** prm.p, prm.tmax), 4)


def reduction_cumulee(brut_cumule: float, smic_cumule: float, prm: Parametres) -> float:
    return round(brut_cumule * coefficient(brut_cumule, smic_cumule, prm), 2)


def reduction_du_mois(brut_prec: float, smic_prec: float, deja_appliquee: float,
                      brut_mois: float, smic_mois: float, prm: Parametres) -> float:
    return round(reduction_cumulee(brut_prec + brut_mois, smic_prec + smic_mois, prm) - deja_appliquee, 2)


def smic_pour_reduction(brut_cumule: float, reduction_voulue: float, prm: Parametres) -> float:
    """Le SMIC cumulé qui redonne `reduction_voulue` (positive) sur ce brut : dichotomie.

    Le coefficient plafonne à `Tmax` dès que le SMIC cumulé atteint le brut cumulé
    (au-delà, rien ne change) : la borne haute de la recherche est donc `brut_cumule`,
    et le maximum atteignable est `reduction_cumulee(brut_cumule, brut_cumule, prm)`.
    La dichotomie compare des réductions arrondies au centime (comme le fait
    `reduction_cumulee`), pas des produits bruts non arrondis : comparer du non
    arrondi à une cible arrondie peut ne jamais satisfaire l'égalité même à la borne
    haute, et faisait dériver la recherche en silence vers une valeur arbitraire.

    Le coefficient légal étant arrondi à 4 décimales (D241-7, II), la réduction
    n'évolue que par paliers en fonction du SMIC cumulé — de l'ordre de quelques
    dizaines de centimes pour un brut cumulé de quelques milliers d'euros, pas d'un
    centime. Arrondir naïvement le milieu de la dichotomie au centime peut donc
    retomber du mauvais côté d'un palier et perdre une solution pourtant trouvée :
    on essaie les deux centimes voisins de la borne haute retrouvée, en plus de son
    arrondi naturel, et on garde celui qui redonne le mieux la cible.

    Lève `ValueError` si `reduction_voulue` est nulle, négative, dépasse de plus de
    0,005 € le maximum atteignable, ou si — malgré tout — aucun des candidats ne
    redonne la cible à 0,01 € près : c'est justement le cas que le chantier doit
    détecter, celui d'une réduction déclarée au-delà de ce que la loi permet. Aucune
    valeur ne doit sortir en silence si elle ne redonne pas la réduction demandée.
    L'appelant (tâche 6, `implicite.py`) intercepte cette erreur et marque le mois
    « non calculable ».
    """
    maximum = reduction_cumulee(brut_cumule, brut_cumule, prm)
    if reduction_voulue <= 0 or reduction_voulue > maximum + 0.005:
        raise ValueError(
            f"réduction voulue {reduction_voulue:.2f} € hors de portée : "
            f"maximum atteignable {maximum:.2f} € pour un brut cumulé de {brut_cumule:.2f} €"
        )
    lo, hi = 0.0, brut_cumule
    for _ in range(100):
        mid = (lo + hi) / 2
        if reduction_cumulee(brut_cumule, mid, prm) < reduction_voulue:
            lo = mid
        else:
            hi = mid
    candidats = {round(hi, 2), floor(hi * 100) / 100, ceil(hi * 100) / 100}
    resultat = min(
        candidats,
        key=lambda c: abs(reduction_cumulee(brut_cumule, c, prm) - reduction_voulue),
    )
    if abs(reduction_cumulee(brut_cumule, resultat, prm) - reduction_voulue) > 0.01:
        raise ValueError(
            f"le SMIC cumulé retrouvé ({resultat:.2f} €) ne redonne pas la réduction "
            f"voulue ({reduction_voulue:.2f} €) à 0,01 € près"
        )
    return resultat
