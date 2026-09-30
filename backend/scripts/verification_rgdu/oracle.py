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
    """Le SMIC cumulé (arrondi au centime) dont la réduction est la plus proche de
    `reduction_voulue`, sur ce brut cumulé.

    Le coefficient légal est arrondi à 4 décimales (D241-7, II) : la réduction
    n'évolue donc que par paliers en fonction du SMIC cumulé, de l'ordre de
    `brut_cumule × 0,0001` par palier (environ 2 € pour 20 000 € de brut cumulé). Une
    cible réelle — une réduction déclarée par Quadra sur un cumul qui n'est pas
    exactement celui que donnerait notre formule — tombe donc presque toujours entre
    deux paliers : ce n'est pas une erreur, c'est le constat que mesure
    `ecart_au_palier` (tâches 6 et 10). Voir aussi `sous_le_plancher` : entre 0 et
    Tmin × brut cumulé, ce n'est pas un simple écart de palier mais un trou prévu par
    la loi, bien plus large. Cette fonction ne cherche donc pas une égalité
    exacte : elle retrouve par dichotomie le palier qui encadre la cible (le
    coefficient plafonne dès que le SMIC cumulé atteint le brut cumulé, d'où la borne
    haute de la recherche), puis renvoie, parmi la borne basse et la borne haute de ce
    palier et leurs centimes voisins, celui dont la réduction est la plus proche de la
    cible.

    Lève `ValueError` si `reduction_voulue` est nulle, négative, ou dépasse de plus de
    0,005 € le maximum atteignable (`reduction_cumulee(brut_cumule, brut_cumule, prm)`) :
    ce sont les deux seuls cas hors de portée. L'appelant (tâche 6, `implicite.py`)
    intercepte cette erreur et marque le mois « non calculable ».
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
    candidats = {
        floor(lo * 100) / 100, ceil(lo * 100) / 100,
        floor(hi * 100) / 100, ceil(hi * 100) / 100,
    }
    return min(
        candidats,
        key=lambda c: abs(reduction_cumulee(brut_cumule, c, prm) - reduction_voulue),
    )


def ecart_au_palier(brut_cumule: float, smic_cumule: float, reduction_voulue: float,
                     prm: Parametres) -> float:
    """Écart, en euros, entre la réduction obtenue pour `smic_cumule` et `reduction_voulue`.

    Positif si `reduction_cumulee(...)` dépasse la cible, négatif sinon. Ce n'est pas
    une erreur : le coefficient légal étant arrondi à 4 décimales (D241-7, II), la
    réduction n'évolue que par paliers, et une cible réelle tombe presque toujours
    entre deux paliers. Cet écart est lui-même le constat que publient les tâches 6
    et 10. Exception : quand `sous_le_plancher(brut_cumule, reduction_voulue, prm)`
    est vrai, l'écart ici renvoyé n'est pas un bruit d'arrondi de palier mais la
    mesure d'un cumul tombé dans le trou légal entre 0 et Tmin × brut cumulé.
    """
    return round(reduction_cumulee(brut_cumule, smic_cumule, prm) - reduction_voulue, 2)


def sous_le_plancher(brut_cumule: float, reduction_voulue: float, prm: Parametres) -> bool:
    """True si `reduction_voulue` tombe dans le trou légal entre 0 et Tmin × brut cumulé.

    Juste avant la sortie à 3 SMIC, le coefficient vaut Tmin (crochet proche de 0,
    `Tmin + Tdelta × crochet^P ≈ Tmin`) ; à 3 SMIC et au-delà, le test de sortie le
    fait sauter à 0 (D241-7, III : « devient nulle » ; regles.md, R-F1 : « à
    exactement 3 SMIC, la formule seule donnerait Tmin »). La loi ne permet donc
    aucune réduction strictement comprise entre 0 et `round(brut_cumule * prm.tmin, 2)` :
    un cumul Quadra qui y tombe est un constat à part, pas un écart de palier
    ordinaire (le trou va jusqu'à Tmin × brut cumulé, bien plus large qu'un palier de
    `brut_cumule × 0,0001`).
    """
    plancher = round(brut_cumule * prm.tmin, 2)
    return 0 < reduction_voulue < plancher - 0.005
