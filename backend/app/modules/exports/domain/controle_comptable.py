"""Contrôle des écritures de paie : équilibre et complétude, au centime.

Trois questions, posées sans I/O sur les bulletins lus et les écritures
produites pour un mois et une société :

1. L'export est-il équilibré (débits = crédits) ?
2. Chaque bulletin se retrouve-t-il entier ? Son net à payer doit se
   reconstruire à partir de ce qu'on en lit : brut − cotisations salariales −
   PAS + éléments hors brut (signés). Un écart est un montant du bulletin que
   l'export ne sait pas classer, ou un bulletin incohérent.
3. Par nature (brut, net, PAS, charges et dettes par organisme, chaque famille
   d'éléments hors brut), la somme de l'export égale-t-elle la somme des
   bulletins ? Un écart est un montant non posté, posté deux fois, ou posté
   sous une autre nature.

Convention de signe : un montant de nature est mesuré comme l'export le
porte, débit moins crédit.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from typing import Any

TOLERANCE = 0.005


def _f(valeur: Any) -> float:
    try:
        return float(valeur or 0)
    except (TypeError, ValueError):
        return 0.0


def residu_du_bulletin(ligne: Mapping[str, Any]) -> float:
    """Net reconstruit moins net à payer du bulletin ; zéro s'il est complet.

    `ligne` est un bulletin tel que l'OD le lit (`ligne_od_du_bulletin`).
    """
    cotisations_salariales = sum(
        _f(c.get("montant_salarial"))
        for c in ligne.get("cotisations_detail") or []
        if isinstance(c, Mapping)
    )
    elements = sum(
        _f(e.get("montant"))
        for e in ligne.get("elements_hors_brut") or []
        if isinstance(e, Mapping)
    )
    reconstruit = (
        _f(ligne.get("brut")) - cotisations_salariales - _f(ligne.get("pas")) + elements
    )
    return round(reconstruit - _f(ligne.get("net_a_payer")), 2)


def natures_des_bulletins(
    lignes: Iterable[Mapping[str, Any]],
    organisme_de: Any,
) -> dict[str, float]:
    """Somme des bulletins par nature, au signe de l'export (débit − crédit).

    `organisme_de(coti)` rattache une ligne de cotisation à son organisme.
    """
    natures: dict[str, float] = defaultdict(float)
    for ligne in lignes:
        natures["brut"] += _f(ligne.get("brut"))
        natures["net_a_payer"] -= _f(ligne.get("net_a_payer"))
        natures["pas"] -= _f(ligne.get("pas"))
        for coti in ligne.get("cotisations_detail") or []:
            if not isinstance(coti, Mapping):
                continue
            organisme = organisme_de(coti)
            patronal = _f(coti.get("montant_patronal"))
            salarial = _f(coti.get("montant_salarial"))
            natures[f"charges:{organisme}"] += patronal
            natures[f"dettes:{organisme}"] -= patronal + salarial
        for element in ligne.get("elements_hors_brut") or []:
            if isinstance(element, Mapping):
                natures[f"hors_brut:{element.get('famille')}"] += _f(element.get("montant"))
    return {k: round(v, 2) for k, v in natures.items() if abs(v) >= TOLERANCE}


def natures_de_l_export(ecritures: Iterable[Mapping[str, Any]]) -> dict[str, float]:
    """Somme des écritures par nature, débit moins crédit."""
    natures: dict[str, float] = defaultdict(float)
    for e in ecritures:
        natures[str(e.get("nature") or "sans_nature")] += _f(e.get("debit")) - _f(
            e.get("credit")
        )
    return {k: round(v, 2) for k, v in natures.items() if abs(v) >= TOLERANCE}


def controler(
    lignes: list[Mapping[str, Any]],
    ecritures: list[Mapping[str, Any]],
    organisme_de: Any,
) -> dict[str, Any]:
    """Rapport de contrôle d'un export : équilibre, complétude, natures."""
    total_debit = round(sum(_f(e.get("debit")) for e in ecritures), 2)
    total_credit = round(sum(_f(e.get("credit")) for e in ecritures), 2)
    bulletins = natures_des_bulletins(lignes, organisme_de)
    export = natures_de_l_export(ecritures)
    natures = []
    for nature in sorted(set(bulletins) | set(export)):
        b, x = bulletins.get(nature, 0.0), export.get(nature, 0.0)
        natures.append(
            {"nature": nature, "bulletins": b, "export": x, "ecart": round(x - b, 2)}
        )
    incoherents = []
    for ligne in lignes:
        residu = residu_du_bulletin(ligne)
        if abs(residu) >= TOLERANCE:
            incoherents.append(
                {"employee_name": ligne.get("employee_name", ""), "residu": residu}
            )
    ecart = round(total_debit - total_credit, 2)
    return {
        "total_debit": total_debit,
        "total_credit": total_credit,
        "ecart": ecart,
        "equilibre": abs(ecart) < TOLERANCE,
        "natures": natures,
        "natures_en_ecart": [n for n in natures if abs(n["ecart"]) >= TOLERANCE],
        "bulletins_incoherents": incoherents,
        "complet": not incoherents
        and all(abs(n["ecart"]) < TOLERANCE for n in natures),
    }
