"""Formule de la réduction générale 2026 (RGDU), écrite depuis les textes (regles.md, R-F1).

Indépendante du moteur : ne rien importer de app/.
"""
from __future__ import annotations

from dataclasses import dataclass


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

    Lève `ValueError` si `reduction_voulue` est nulle, négative, ou dépasse le
    maximum atteignable (`brut_cumule * prm.tmax`) : c'est justement le cas que le
    chantier doit détecter, celui d'une réduction déclarée au-delà de ce que la loi
    permet. Sans cette garde, la dichotomie convergerait en silence vers une borne
    haute arbitraire (environ deux fois le brut cumulé) au lieu de signaler
    l'anomalie. L'appelant (tâche 6, `implicite.py`) intercepte cette erreur et
    marque le mois « non calculable ».
    """
    maximum = round(brut_cumule * prm.tmax, 2)
    if reduction_voulue <= 0 or reduction_voulue > maximum + 0.005:
        raise ValueError(
            f"réduction voulue {reduction_voulue:.2f} € hors de portée : "
            f"maximum atteignable {maximum:.2f} € pour un brut cumulé de {brut_cumule:.2f} €"
        )
    lo, hi = 0.0, brut_cumule * 2
    for _ in range(100):
        mid = (lo + hi) / 2
        if brut_cumule * coefficient(brut_cumule, mid, prm) < reduction_voulue:
            lo = mid
        else:
            hi = mid
    return round((lo + hi) / 2, 2)
