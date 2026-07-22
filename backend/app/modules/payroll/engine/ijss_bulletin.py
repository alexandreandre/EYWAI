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


def build_rappel_ijss_net_prime(
    *,
    prime_id: str,
    libelle: str,
    montant: float,
    baremes_maladie: Dict[str, Any] | None,
) -> Dict[str, Any] | None:
    """Construit la contrepartie nette d'un rappel d'IJSS déduit du brut.

    Sur un bulletin de régularisation, la rubrique négative « Rappel IJSS »
    corrige le brut et les assiettes du mois courant. Sa contrepartie « IJSS
    nettes » restitue au salarié le rappel brut diminué de la CSG/CRDS sur
    revenus de remplacement, sans réintégrer ce montant au net imposable du
    mois (il se rapporte à une période antérieure).
    """
    label = f"{prime_id} {libelle}".lower()
    amount = float(montant or 0.0)
    if amount >= 0 or "rappel" not in label or "ijss" not in label:
        return None

    _, _, net_ijss = compute_ijss_csg_lines(abs(amount), baremes_maladie)
    if net_ijss <= 0:
        return None
    return {
        "prime_id": "rappel_ijss_net",
        "libelle": "IJSS nettes (rappel)",
        "montant": net_ijss,
        "is_rappel_ijss": True,
    }
