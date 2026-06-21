"""
Calcul des exonérations frais professionnels et indemnités kilométriques (fonctions pures).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple


def exoneration_repas(
    frais_pro: Optional[Dict[str, Any]],
    type_repas: str = "repas",
) -> Optional[float]:
    """
    Retourne le plafond d'exonération repas (€) depuis frais_pro.sections.repas.
    None si barème absent.
    """
    if not frais_pro or not isinstance(frais_pro, dict):
        return None
    sections = frais_pro.get("sections") or {}
    repas = sections.get(type_repas) or sections.get("repas") or {}
    if not isinstance(repas, dict):
        return None
    for key in (
        "repas",
        "montant",
        "forfait",
        "valeur",
        "indemnite_repas",
        "repas_valeur",
    ):
        val = repas.get(key)
        if isinstance(val, (int, float)) and val > 0:
            return float(val)
    vals = [float(v) for v in repas.values() if isinstance(v, (int, float)) and v > 0]
    return max(vals) if vals else None


def reintegration_exces(montant_saisi: float, plafond: Optional[float]) -> float:
    """Fraction excédentaire à réintégrer au brut (0 si plafond inconnu)."""
    if plafond is None:
        return 0.0
    return max(0.0, float(montant_saisi) - float(plafond))


def _match_cv_tranche(
    tranches: List[Dict[str, Any]], puissance_cv: float
) -> Optional[Dict[str, Any]]:
    cv = int(round(puissance_cv))
    for tr in tranches:
        cv_min = tr.get("cv_min")
        cv_max = tr.get("cv_max")
        mn = float("-inf") if cv_min is None else int(cv_min)
        mx = float("inf") if cv_max is None else int(cv_max)
        if mn <= cv <= mx:
            return tr
    return tranches[0] if tranches else None


def _pick_segment_formula(
    distance: float, segments: List[Dict[str, Any]], formules: List[Dict[str, Any]]
) -> Optional[Tuple[float, float]]:
    if not formules:
        return None
    seg_idx = 0
    if segments:
        for i, seg in enumerate(segments):
            d_min = seg.get("d_min") or 0
            d_max = seg.get("d_max")
            if distance >= d_min and (d_max is None or distance <= d_max):
                seg_idx = i
                break
        else:
            seg_idx = len(segments) - 1
    if seg_idx >= len(formules):
        seg_idx = len(formules) - 1
    f = formules[seg_idx]
    a = f.get("a")
    b = f.get("b")
    if a is None:
        return None
    return float(a), float(b or 0.0)


def indemnite_km(
    baremes_km: Optional[Dict[str, Any]],
    type_vehicule: str,
    puissance_cv: float,
    distance: float,
) -> Optional[float]:
    """
    Montant indemnité kilométrique exonérée selon le barème scrapé.
    type_vehicule : voitures | motocyclettes | cyclomoteurs
    """
    if not baremes_km or distance <= 0:
        return None
    vehicules = baremes_km.get("vehicules") or {}
    key_map = {
        "voiture": "voitures",
        "voitures": "voitures",
        "moto": "motocyclettes",
        "motocyclettes": "motocyclettes",
        "cyclo": "cyclomoteurs",
        "cyclomoteurs": "cyclomoteurs",
    }
    block_key = key_map.get(type_vehicule.lower(), type_vehicule.lower())
    block = vehicules.get(block_key)
    if not isinstance(block, dict):
        return None
    tranches = block.get("tranches_cv") or []
    tranche = _match_cv_tranche(tranches, puissance_cv)
    if not tranche:
        return None
    formules = tranche.get("formules") or []
    segments = block.get("segments") or []
    picked = _pick_segment_formula(distance, segments, formules)
    if not picked:
        return None
    a, b = picked
    return round(distance * a + b, 2)


def coefficient_a_km(
    baremes_km: Optional[Dict[str, Any]],
    type_vehicule: str,
    puissance_cv: float,
    *,
    segment_index: int = 0,
) -> Optional[float]:
    """Coefficient €/km (formule a×d+b) pour un segment du barème fiscal."""
    if not baremes_km:
        return None
    vehicules = baremes_km.get("vehicules") or {}
    key_map = {
        "voiture": "voitures",
        "voitures": "voitures",
        "moto": "motocyclettes",
        "motocyclettes": "motocyclettes",
        "cyclo": "cyclomoteurs",
        "cyclomoteurs": "cyclomoteurs",
    }
    block_key = key_map.get(type_vehicule.lower(), type_vehicule.lower())
    block = vehicules.get(block_key)
    if not isinstance(block, dict):
        return None
    tranches = block.get("tranches_cv") or []
    tranche = _match_cv_tranche(tranches, puissance_cv)
    if not tranche:
        return None
    formules = tranche.get("formules") or []
    if not formules:
        return None
    idx = min(max(0, segment_index), len(formules) - 1)
    a = formules[idx].get("a")
    if a is None:
        return None
    return float(a)


def indemnite_km_astreinte(
    baremes_km: Optional[Dict[str, Any]],
    distance_one_way: float,
    vehicle_cv: float,
    vehicle_type: str,
    *,
    threshold_one_way: float = 10.0,
    round_trip_multiplier: float = 2.0,
    rate_mode: str = "coefficient_a",
    bareme_segment_index: int = 0,
) -> tuple[Optional[float], dict[str, Any]]:
    """
    Indemnité km astreinte (franchise aller simple + multiplicateur AR).
    Retourne (montant arrondi ou None, détails calcul).
    """
    details: dict[str, Any] = {
        "distance_km_one_way": distance_one_way,
        "threshold_one_way": threshold_one_way,
        "round_trip_multiplier": round_trip_multiplier,
        "rate_mode": rate_mode,
    }
    eligible_one_way = max(0.0, float(distance_one_way) - float(threshold_one_way))
    details["km_eligible_one_way"] = round(eligible_one_way, 2)
    if eligible_one_way <= 0:
        details["skip_reason"] = "below_threshold"
        return None, details
    distance = eligible_one_way * float(round_trip_multiplier)
    details["km_eligible"] = round(distance, 2)
    if rate_mode == "coefficient_a":
        rate = coefficient_a_km(
            baremes_km,
            vehicle_type,
            vehicle_cv,
            segment_index=bareme_segment_index,
        )
        if rate is None:
            details["skip_reason"] = "bareme_missing"
            return None, details
        details["rate"] = rate
        amount = round(distance * rate, 2)
        details["unit_amount"] = amount
        return amount, details
    amount = indemnite_km(baremes_km, vehicle_type, vehicle_cv, distance)
    if amount is None:
        details["skip_reason"] = "bareme_missing"
        return None, details
    details["unit_amount"] = amount
    return amount, details


def appliquer_exoneration_note_frais(
    saisie: Dict[str, Any],
    frais_pro: Optional[Dict[str, Any]],
) -> Tuple[float, float, Optional[float]]:
    """
    Retourne (montant_exonere, montant_reintegre, plafond).
    type note : repas / panier / hebergement via saisie['type'] ou prime_id.
    """
    montant = float(saisie.get("montant") or 0.0)
    if montant <= 0:
        return 0.0, 0.0, None
    type_ndf = str(
        saisie.get("type")
        or saisie.get("prime_id")
        or "repas"
    ).lower()
    if "repas" in type_ndf or "panier" in type_ndf:
        plafond = exoneration_repas(frais_pro, "repas")
    else:
        plafond = None
    if plafond is None:
        return montant, 0.0, None
    exo = min(montant, plafond)
    reint = reintegration_exces(montant, plafond)
    return exo, reint, plafond
