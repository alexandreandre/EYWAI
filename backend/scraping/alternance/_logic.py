"""Signature / comparaison / merge sûr pour le régime alternance (apprenti).

Le bloc payroll_config « alternance » est une donnée réglementaire structurée et
sensible (régimes datés apprenti, codes DSN, professionnalisation). Ce scraper ne
vérifie que quelques valeurs scalaires mutables (seuil d'exonération salariale en
% du SMIC du régime EN VIGUEUR, plafond d'exonération IR) et les FUSIONNE dans la
config existante — il ne reconstruit jamais la structure et ne supprime aucune clé.
"""

from __future__ import annotations

import copy
import math
from typing import Any, Dict, Optional

from core.validation import ValidationResult, require_float_range, validate_all


def _payload_valeurs(payload: Dict[str, Any]) -> Dict[str, Any]:
    return payload.get("valeurs") or payload.get("sections") or {}


def core_signature(payload: Dict[str, Any]) -> Dict[str, Any]:
    v = _payload_valeurs(payload)
    return {
        "apprenti_exo_pct_smic": v.get("apprenti_exo_pct_smic"),
        "apprenti_ir_plafond_pct_smic": v.get("apprenti_ir_plafond_pct_smic"),
    }


def _eq(a: Any, b: Any, tol: float = 1e-9) -> bool:
    if a is None or b is None:
        return a is b
    return math.isclose(float(a), float(b), abs_tol=tol)


def signatures_equal(a: Dict[str, Any], b: Dict[str, Any]) -> bool:
    return _eq(
        a.get("apprenti_exo_pct_smic"), b.get("apprenti_exo_pct_smic")
    ) and _eq(
        a.get("apprenti_ir_plafond_pct_smic"), b.get("apprenti_ir_plafond_pct_smic")
    )


def validate_signature(sig: Dict[str, Any]) -> ValidationResult:
    return validate_all(
        [
            lambda: require_float_range(
                sig.get("apprenti_exo_pct_smic"),
                name="apprenti_exo_pct_smic",
                min_v=0.3,
                max_v=1.0,
            ),
            lambda: require_float_range(
                sig.get("apprenti_ir_plafond_pct_smic"),
                name="apprenti_ir_plafond_pct_smic",
                min_v=0.5,
                max_v=1.5,
            ),
        ]
    )


def build_config_data(
    sig: Dict[str, Any], current: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    """Fusionne les scalaires vérifiés dans la config alternance existante.

    Ne fabrique jamais la structure : sans config active, on refuse d'écrire
    (protège un bloc réglementaire sensible d'un écrasement partiel).
    """
    cur = (current or {}).get("config_data") if current else None
    if not isinstance(cur, dict) or not isinstance(cur.get("apprenti"), dict):
        raise ValueError("Config alternance active requise pour un merge sûr")

    data = copy.deepcopy(cur)
    apprenti = data["apprenti"]

    # Régime EN VIGUEUR = borne haute d'exécution ouverte (date_execution_max null).
    regimes = apprenti.get("regimes") or []
    en_vigueur = [r for r in regimes if r.get("date_execution_max") in (None, "")]
    target = en_vigueur[-1] if en_vigueur else (regimes[-1] if regimes else None)
    pct = sig.get("apprenti_exo_pct_smic")
    if target is not None and pct is not None:
        target["plafond_exoneration_pct_smic"] = float(pct)

    ir_pct = sig.get("apprenti_ir_plafond_pct_smic")
    if ir_pct is not None:
        ir = apprenti.setdefault("exoneration_ir", {})
        ir["plafond_annuel_pct_smic"] = float(ir_pct)

    return data


def signature_for_emit(sig: Dict[str, Any]) -> Dict[str, Any]:
    return dict(sig)
