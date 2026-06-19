"""Calcul CSG/CRDS sur IJSS subrogées (partagé heures / forfait)."""

from __future__ import annotations

from typing import Any, Dict, List, Tuple


def compute_ijss_csg_lines(
    ijss_brut: float, baremes_maladie: Dict[str, Any] | None
) -> Tuple[List[Dict[str, Any]], float, float]:
    """
    Retourne (lignes_csg_ijss, total_csg, net_ijss_apres_csg).

    Le net IJSS = brut - CSG/CRDS salariales sur IJSS.
    """
    base = round(float(ijss_brut or 0), 2)
    if base <= 0:
        return [], 0.0, 0.0

    cfg_csg = (baremes_maladie or {}).get("csg_ijss", {}) or {}
    taux_deductible = float(cfg_csg.get("taux_deductible", 0.038))
    taux_non_deductible = float(cfg_csg.get("taux_non_deductible", 0.029))
    csg_deductible = round(base * taux_deductible, 2)
    csg_non_deductible = round(base * taux_non_deductible, 2)
    total_csg = round(csg_deductible + csg_non_deductible, 2)
    net_ijss = round(base - total_csg, 2)

    lignes: List[Dict[str, Any]] = []
    if csg_deductible > 0:
        lignes.append(
            {
                "libelle": "CSG déductible IJSS",
                "base": base,
                "taux_salarial": taux_deductible,
                "montant_salarial": csg_deductible,
                "taux_patronal": 0.0,
                "montant_patronal": 0.0,
            }
        )
    if csg_non_deductible > 0:
        lignes.append(
            {
                "libelle": "CSG/CRDS IJSS non déductible",
                "base": base,
                "taux_salarial": taux_non_deductible,
                "montant_salarial": csg_non_deductible,
                "taux_patronal": 0.0,
                "montant_patronal": 0.0,
            }
        )
    return lignes, total_csg, net_ijss
