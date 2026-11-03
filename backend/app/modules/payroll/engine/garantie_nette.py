"""Garantie du net d'un maintien conventionnel (conception du 03/11/2026).

La plasturgie garantit « la rémunération nette qu'aurait perçue l'intéressé »
(avenant du 15/05/1991, art. 13 e ; accord Cadres du 17/12/1992, art. 5). Les
IJ ne supportent que la CSG et la CRDS ; le salaire, toutes les cotisations
salariales. Pour que le net reçu soit le net garanti, les IJ déduites sont
comptées nettes, puis ramenées au brut avec la part salariale du salarié :

    versé × (1 − t) + IJ × (1 − s) = garanti × (1 − t)
    ⇔ versé = garanti − IJ × (1 − s) / (1 − t)

`t` est mesuré par le moteur de cotisations lui-même, sans recopier un taux.
"""

from __future__ import annotations

import copy
import logging
from collections.abc import Mapping
from typing import Any

logger = logging.getLogger(__name__)

#: CSG (3,8 % déductible + 2,4 % non déductible) et CRDS (0,5 %) des IJ : les
#: défauts de `compute_ijss_csg_lines`, qui pose ces lignes au bulletin.
TAUX_DEDUCTIBLE_IJSS = 0.038
TAUX_NON_DEDUCTIBLE_IJSS = 0.029
#: Au-delà, la mesure est jugée fausse : la lecture brute est gardée.
TAUX_SALARIAL_MAXIMUM = 0.6


def taux_csg_crds_ijss(baremes_maladie: Mapping[str, Any] | None) -> float:
    """Le taux de CSG et CRDS des IJ, lu comme les lignes du bulletin."""
    cfg = (baremes_maladie or {}).get("csg_ijss") or {}
    return float(cfg.get("taux_deductible", TAUX_DEDUCTIBLE_IJSS)) + float(
        cfg.get("taux_non_deductible", TAUX_NON_DEDUCTIBLE_IJSS)
    )


def ijss_ramenees_au_brut(ijss_brutes: float, taux_ijss: float, taux_salarial: float) -> float:
    """Le salaire brut qui laisse le même net que ces IJ."""
    if ijss_brutes <= 0:
        return 0.0
    return round(ijss_brutes * (1 - taux_ijss) / (1 - taux_salarial), 2)


def taux_salarial_marginal(contexte: Any, brut_haut: float, ecart: float) -> float | None:
    """La part salariale (cotisations, CSG, CRDS) d'un euro de salaire entre
    `brut_haut − ecart` et `brut_haut`, ou None si elle ne se mesure pas.

    Le calcul se fait sur une copie du contexte, sans journal de corrections :
    une correction manuelle ne se consomme qu'une fois, sur le vrai bulletin.
    """
    if ecart <= 0 or brut_haut <= 0:
        return None
    from .calcul_cotisations import calculer_cotisations

    try:
        sonde = copy.copy(contexte)
        sonde.corrections_du_mois = None
        _, haut = calculer_cotisations(sonde, round(brut_haut, 2))
        sonde = copy.copy(contexte)
        sonde.corrections_du_mois = None
        _, bas = calculer_cotisations(sonde, round(max(0.0, brut_haut - ecart), 2))
    except Exception:
        logger.exception("Garantie du net : taux de cotisations salariales non mesuré")
        return None
    taux = (float(haut) - float(bas)) / ecart
    if not 0.0 <= taux < TAUX_SALARIAL_MAXIMUM:
        return None
    return taux


__all__ = [
    "TAUX_SALARIAL_MAXIMUM",
    "ijss_ramenees_au_brut",
    "taux_csg_crds_ijss",
    "taux_salarial_marginal",
]
