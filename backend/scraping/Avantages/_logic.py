"""Normalisation, comparaison et build pour avantages en nature."""

from __future__ import annotations

import logging
import math
from typing import Any, Dict, List, Optional

from core.validation import ValidationResult

logger = logging.getLogger(__name__)


def to_float(x: Any) -> float | None:
    if x is None:
        return None
    try:
        if isinstance(x, str):
            x = (
                x.replace("\u202f", "")
                .replace("\xa0", "")
                .replace("€", "")
                .replace(" ", "")
                .replace(",", ".")
            )
        return float(x)
    except (ValueError, TypeError):
        return None


def normalize_bareme(lst: Any) -> List[Dict[str, float]]:
    out: List[Dict[str, float]] = []
    if not isinstance(lst, list):
        return out
    for row in lst:
        if not isinstance(row, dict):
            continue
        rmax = to_float(row.get("remuneration_max") or row.get("remuneration_max_eur"))
        v1 = to_float(row.get("valeur_1_piece") or row.get("valeur_1_piece_eur"))
        vpp = to_float(
            row.get("valeur_par_piece") or row.get("valeur_par_piece_suppl_eur")
        )
        if v1 is None or vpp is None:
            logger.warning("Ligne de barème logement ignorée (données manquantes): %s", row)
            continue
        out.append(
            {
                "remuneration_max_eur": rmax if rmax is not None else 9_999_999.99,
                "valeur_1_piece_eur": v1,
                "valeur_par_piece_suppl_eur": vpp,
            }
        )
    return sorted(out, key=lambda x: x["remuneration_max_eur"])


def payload_to_core(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Extrait le noyau comparable (repas, titre, logement) depuis divers formats."""
    core: Dict[str, Any] = {"repas": None, "titre": None, "logement": [], "__src": []}
    script_name = payload.get("__script", "unknown")

    try:
        if isinstance(payload, dict) and payload.get("type") == "param_bundle":
            items = payload.get("items", [])
            mp = {
                it.get("key"): it.get("value") for it in items if isinstance(it, dict)
            }
            core["repas"] = to_float(
                mp.get("repas_valeur_forfaitaire_eur") or mp.get("repas")
            )
            core["titre"] = to_float(
                mp.get("titre_restaurant_exoneration_max_eur")
                or mp.get("titre_restaurant")
            )
            core["logement"] = normalize_bareme(
                mp.get("logement_bareme_forfaitaire") or mp.get("logement")
            )
            core["__src"] = payload.get("meta", {}).get("source", [])
            return core

        if isinstance(payload, dict) and {
            "repas",
            "titre_restaurant",
            "logement",
        } <= set(payload.keys()):
            core["repas"] = to_float(payload.get("repas"))
            core["titre"] = to_float(payload.get("titre_restaurant"))
            core["logement"] = normalize_bareme(payload.get("logement"))
            core["__src"] = payload.get("meta", {}).get("source", [])
            return core

        av = payload.get("PARAMETRES_ENTREPRISE", {}).get("avantages_en_nature", {})
        if not av:
            av = (
                payload.get("entreprise", {})
                .get("parametres_paie", {})
                .get("avantages_en_nature", {})
            )

        if av:
            core["repas"] = to_float(av.get("repas_valeur_forfaitaire"))
            core["titre"] = to_float(
                av.get("titre_restaurant_exoneration_max_patronale")
            )
            core["logement"] = normalize_bareme(av.get("logement_bareme_forfaitaire"))
            return core

        logger.warning(
            "Format de payload non reconnu pour %s. Tentative d'extraction échouée.",
            script_name,
        )
    except Exception as e:
        logger.error(
            "Erreur lors de la normalisation du payload pour %s: %s",
            script_name,
            e,
        )

    return core


def compare_floats(a: float | None, b: float | None, tol: float = 1e-9) -> bool:
    if a is None or b is None:
        return a is b
    try:
        return math.isclose(float(a), float(b), abs_tol=tol)
    except (ValueError, TypeError):
        return False


def cores_equal(a: Dict[str, Any], b: Dict[str, Any], tol: float = 1e-6) -> bool:
    if not (
        compare_floats(a["repas"], b["repas"], tol)
        and compare_floats(a["titre"], b["titre"], tol)
    ):
        return False

    la, lb = a["logement"], b["logement"]
    if len(la) != len(lb):
        return False

    for r1, r2 in zip(la, lb):
        if not (
            compare_floats(r1["remuneration_max_eur"], r2["remuneration_max_eur"], tol)
            and compare_floats(r1["valeur_1_piece_eur"], r2["valeur_1_piece_eur"], tol)
            and compare_floats(
                r1["valeur_par_piece_suppl_eur"], r2["valeur_par_piece_suppl_eur"], tol
            )
        ):
            return False

    return True


def logement_values_equal(a: List[Dict[str, float]], b: List[Dict[str, float]], tol: float = 1e-6) -> bool:
    """Compare le barème logement sur les montants forfaitaires (pas le plafond de tranche)."""
    la, lb = normalize_bareme(a), normalize_bareme(b)
    if len(la) != len(lb):
        return False
    for r1, r2 in zip(la, lb):
        if not compare_floats(r1["valeur_1_piece_eur"], r2["valeur_1_piece_eur"], tol):
            return False
        if not compare_floats(
            r1["valeur_par_piece_suppl_eur"], r2["valeur_par_piece_suppl_eur"], tol
        ):
            return False
    return True


def validate_signature(sig: Dict[str, Any]) -> ValidationResult:
    if sig.get("repas") is None:
        return ValidationResult(False, "repas manquant")
    if sig.get("titre") is None:
        return ValidationResult(False, "titre restaurant manquant")
    if not sig.get("logement"):
        return ValidationResult(False, "barème logement vide")
    return ValidationResult(True)


def build_config_data(sig: Dict[str, Any], _current: Optional[dict]) -> Dict[str, Any]:
    out = dict(sig)
    out.pop("__src", None)
    return out


def signature_for_emit(sig: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(sig)
    out.pop("__src", None)
    return out
