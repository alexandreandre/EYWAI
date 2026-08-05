"""Extraction comptable depuis payslip_data (formats bulletin récents et legacy)."""
from __future__ import annotations

from typing import Any, Dict, List, Tuple


def extract_pas_amount(synthese_net: Any) -> float:
    if not isinstance(synthese_net, dict):
        return 0.0
    pas_obj = synthese_net.get("impot_prelevement_a_la_source")
    if isinstance(pas_obj, dict):
        return float(pas_obj.get("montant", 0) or 0)
    legacy = synthese_net.get("impot_preleve_a_la_source")
    if legacy is not None:
        return float(legacy or 0)
    return 0.0


def _flatten_cotisation_lines(structure_cotisations: Dict[str, Any]) -> List[Dict[str, Any]]:
    lines: List[Dict[str, Any]] = []

    legacy = structure_cotisations.get("cotisations")
    if isinstance(legacy, list) and legacy:
        return [c for c in legacy if isinstance(c, dict)]

    for key in ("bloc_principales", "bloc_allegements", "bloc_csg_non_deductible"):
        bloc = structure_cotisations.get(key)
        if isinstance(bloc, list):
            lines.extend(c for c in bloc if isinstance(c, dict))

    autres = structure_cotisations.get("bloc_autres_contributions")
    if isinstance(autres, dict):
        extra = autres.get("lignes")
        if isinstance(extra, list):
            lines.extend(c for c in extra if isinstance(c, dict))

    return lines


def extract_elements_hors_brut(payslip_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Éléments qui s'ajoutent au net à payer sans transiter par le brut.

    Primes non soumises, retenues, et participation. Sans contrepartie au débit,
    l'OD est déséquilibrée d'exactement leur total — c'est la cause de l'écart
    constaté sur les OD générées jusqu'ici.

    Chaque élément porte sa `famille`, clé stable de rattachement comptable :
    `prime_id` et le libellé sont du texte libre saisi par la RH et ne peuvent
    pas servir de clé.
    """
    from app.modules.exports.domain.accounting_plan import (
        FAMILLE_PARTICIPATION,
        FAMILLE_PARTICIPATION_PEE,
        resolve_element_family,
    )

    elements: List[Dict[str, Any]] = []

    for prime in payslip_data.get("primes_non_soumises") or []:
        if not isinstance(prime, dict):
            continue
        montant = float(prime.get("montant", 0) or 0)
        if montant == 0:
            continue
        libelle = str(prime.get("libelle") or "")
        prime_id = prime.get("prime_id")
        elements.append(
            {
                "famille": resolve_element_family(libelle, prime_id),
                "libelle": libelle or "Élément hors brut",
                "montant": montant,
            }
        )

    for part in payslip_data.get("participations") or []:
        if not isinstance(part, dict):
            continue
        brut = float(part.get("brut", 0) or 0)
        part_pee = float(part.get("part_pee", 0) or 0)
        libelle = str(part.get("libelle") or "Participation")
        # Le brut de participation est la charge ; la CSG figure déjà parmi les
        # cotisations, et la part placée sur un PEE ne va pas au net à payer.
        if brut != 0:
            elements.append(
                {
                    "famille": FAMILLE_PARTICIPATION,
                    "libelle": libelle,
                    "montant": brut,
                }
            )
        if part_pee != 0:
            elements.append(
                {
                    "famille": FAMILLE_PARTICIPATION_PEE,
                    "libelle": f"{libelle} — part placée sur un plan d'épargne",
                    "montant": -part_pee,
                }
            )

    return elements


def extract_cotisations_from_payslip(
    payslip_data: Dict[str, Any],
) -> Tuple[float, float, List[Dict[str, Any]], Dict[str, Any]]:
    """
    Retourne (cot_sal, cot_pat, lignes détail, meta diagnostic).
    """
    meta: Dict[str, Any] = {"format": "unknown", "warnings": []}
    sc = payslip_data.get("structure_cotisations")
    if not isinstance(sc, dict):
        meta["warnings"].append("structure_cotisations absente ou invalide")
        return 0.0, 0.0, [], meta

    legacy_list = sc.get("cotisations")
    if isinstance(legacy_list, list) and legacy_list:
        meta["format"] = "legacy_cotisations_list"
        cot_sal = sum(float(c.get("montant_salarial", 0) or 0) for c in legacy_list if isinstance(c, dict))
        cot_pat = sum(float(c.get("montant_patronal", 0) or 0) for c in legacy_list if isinstance(c, dict))
        return cot_sal, cot_pat, [c for c in legacy_list if isinstance(c, dict)], meta

    meta["format"] = "bulletin_blocs"
    cot_sal = float(sc.get("total_salarial", 0) or 0)
    cot_pat = float(sc.get("total_patronal", 0) or 0)
    detail = _flatten_cotisation_lines(sc)

    if cot_sal == 0 and cot_pat == 0 and not detail:
        meta["warnings"].append(
            "total_salarial/total_patronal à 0 et aucune ligne de cotisation extraite"
        )

    return cot_sal, cot_pat, detail, meta
