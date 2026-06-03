"""Normalisation, comparaison et build pour prévoyance cadre / non-cadre."""

from __future__ import annotations

import json
import logging
import math
from typing import Any, Dict, Optional

from cotisation_sync import (
    new_cotisation_item,
    should_apply_cotisation_patch,
    stamp_cotisation_inplace,
)
from core.validation import ValidationResult, require_patronal_rate

logger = logging.getLogger(__name__)


def _normalize_block(block: Dict[str, Any], expected_id: str) -> Dict[str, Any]:
    if block.get("id") != expected_id:
        raise ValueError(f"ID '{expected_id}' attendu, reçu '{block.get('id')}'")
    valeurs = block.get("valeurs") or {}
    patro_raw = valeurs.get("patronal")
    sal_raw = valeurs.get("salarial")
    patro = round(float(patro_raw), 6) if patro_raw is not None else None
    sal = round(float(sal_raw), 6) if sal_raw is not None else None
    return {
        "id": block.get("id"),
        "libelle": block.get("libelle"),
        "base": block.get("base"),
        "preserve_rates": bool(block.get("preserve_rates")),
        "valeurs": {"salarial": sal, "patronal": patro},
    }


def branch_signature(
    payload: Dict[str, Any], branch_key: str, item_id: str
) -> Dict[str, Any]:
    branch = payload.get(branch_key)
    if not isinstance(branch, dict):
        raise ValueError(f"Payload invalide : '{branch_key}' requis.")
    return _normalize_block(branch, item_id)


def compare_floats(a: float | None, b: float | None, tol: float = 1e-9) -> bool:
    if a is None or b is None:
        return a is b
    try:
        return math.isclose(float(a), float(b), abs_tol=tol)
    except (ValueError, TypeError):
        return False


def equal_branch(a: Dict[str, Any], b: Dict[str, Any], tol: float = 1e-9) -> bool:
    if a.get("preserve_rates") != b.get("preserve_rates"):
        return False
    if a.get("preserve_rates") and b.get("preserve_rates"):
        return True
    va, vb = a["valeurs"], b["valeurs"]
    return compare_floats(va.get("patronal"), vb.get("patronal"), tol) and compare_floats(
        va.get("salarial"), vb.get("salarial"), tol
    )


def accept_payload(branch_key: str):
    def _accept(_label: str, payload: Dict[str, Any]) -> bool:
        branch = payload.get(branch_key)
        if isinstance(branch, dict):
            meta = branch.get("meta") or {}
            payload.setdefault("meta", {})["source"] = meta.get("source", [])
        return True

    return _accept


def validate_cadre(sig: Dict[str, Any]) -> ValidationResult:
    pat = sig["valeurs"].get("patronal")
    return require_patronal_rate(pat, name="prevoyance_cadre patronal")


def validate_non_cadre(_sig: Dict[str, Any]) -> ValidationResult:
    return ValidationResult(True)


def _apply_branch_patch(
    item: Dict[str, Any],
    branch: Dict[str, Any],
    cotisation_id: str,
) -> None:
    if not should_apply_cotisation_patch(cotisation_id):
        return
    if branch.get("preserve_rates"):
        stamp_cotisation_inplace(item, cotisation_id)
        logger.info(
            "Contrôle enregistré pour '%s' (taux inchangés — référence CCN).",
            cotisation_id,
        )
        return
    valeurs = branch["valeurs"]
    if valeurs.get("patronal") is not None:
        item["patronal"] = valeurs["patronal"]
    if valeurs.get("salarial") is not None:
        item["salarial"] = valeurs["salarial"]
    elif "salarial" in valeurs and valeurs["salarial"] is None:
        item["salarial"] = None
    stamp_cotisation_inplace(item, cotisation_id)


def build_config_data(item_id: str):
    def _build(sig: Dict[str, Any], current: Optional[dict]) -> Dict[str, Any]:
        if current and current.get("config_data"):
            new_config_data = json.loads(json.dumps(current["config_data"]))
        else:
            new_config_data = {"cotisations": []}

        cotisations_list = new_config_data.get("cotisations", [])
        found = False

        for item in cotisations_list:
            if isinstance(item, dict) and item.get("id") == item_id:
                found = True
                _apply_branch_patch(item, sig, item_id)
                break

        if should_apply_cotisation_patch(item_id) and not found:
            new_item = new_cotisation_item(
                {
                    "id": item_id,
                    "libelle": sig.get("libelle") or item_id,
                    "base": sig.get("base") or "brut",
                    "salarial": sig["valeurs"].get("salarial"),
                    "patronal": sig["valeurs"].get("patronal"),
                },
                item_id,
            )
            _apply_branch_patch(new_item, sig, item_id)
            cotisations_list.append(new_item)

        new_config_data["cotisations"] = cotisations_list
        return new_config_data

    return _build


def make_extract(branch_key: str, item_id: str):
    return lambda p: branch_signature(p, branch_key, item_id)
